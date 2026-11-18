"""
agents.py - the brain of Nuance.

It contains the four agents plus the ranking step:
  1. Theory-of-Mind agent : guesses what each customer believes, feels and intends
  2. Domain agent         : checks each guess against the review and the brand context
  3. Prioritiser          : counts and ranks the topics (plain Python)
  4. Validation agent     : checks the advice and gives a confidence level
"""

import json
import re
import ollama
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# The model we downloaded with Ollama
MODEL = "llama3.1:8b"


def ask_llama(prompt):
    """Send a prompt to Llama and return its answer as a Python dictionary."""
    reply = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        format="json",
    )
    return json.loads(reply["message"]["content"])


# ---------------------------------------------------------------
# Topics: the list of things customers talk about (you can change it)
# Each line is "topic: short definition". "other" is always added.
# ---------------------------------------------------------------
DEFAULT_TOPICS = """fit: how well it attaches to a hair dryer
durability: it breaks, collapses or wears out
price: cost and value for money
travel: using it while travelling"""


def parse_topics(text):
    """Turn the topics text into a dictionary: {topic: definition}."""
    topics = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        name, _, definition = line.partition(":")
        topics[name.strip().lower()] = definition.strip()
    topics["other"] = "anything that fits none of the topics above"
    return topics


def suggest_topics(reviews, product_info, per_call=10, keep=6):
    """Read a sample of reviews and propose topics. A human edits the result."""
    counts = {}          # how many times each topic name was proposed
    definitions = {}     # the first definition seen for each name

    for start in range(0, len(reviews), per_call):
        batch = reviews[start:start + per_call]
        numbered = "\n".join(f"{i + 1}. {text[:200]}" for i, text in enumerate(batch))
        prompt = f'''These are customer reviews of this product: {product_info}

{numbered}

Name the 3 topics that customers talk about most in these reviews.
Rules:
- "name": 1 or 2 lowercase words.
- "definition": a short phrase with examples of the words customers use.
- Only use topics that the reviews really mention.

Reply with JSON only, in exactly this format:
{{"topics": [{{"name": "one or two words", "definition": "short phrase"}}]}}'''
        try:
            answer = ask_llama(prompt)
        except Exception:
            continue          # skip a batch that failed

        for item in answer.get("topics", []):
            name = str(item.get("name", "")).strip().lower()
            if name == "" or name == "other" or len(name.split()) > 2:
                continue
            counts[name] = counts.get(name, 0) + 1
            definitions.setdefault(name, str(item.get("definition", "")).strip())

    # Python keeps the topics proposed most often
    best = sorted(counts, key=lambda name: counts[name], reverse=True)[:keep]
    return "\n".join(f"{name}: {definitions[name]}" for name in best)


# ---------------------------------------------------------------
# Agent 1: Theory-of-Mind (guess what the customer believes)
# ---------------------------------------------------------------
def theory_of_mind(review, product_info):
    prompt = f'''You are an expert in understanding customers.
Product: {product_info}
Customer review: "{review[:500]}"

Think about what this customer really believes, feels and intends.
Give 2 explanations that are clearly DIFFERENT from each other:
- Explanation 1: the most likely one, based only on what the review says.
- Explanation 2: a different, milder or more mixed possibility (for example, partly happy).
Do not invent facts that are not in the review.

Rules:
- Each "belief" must be about ONE single thing only (for example only the scent, or only the price, or only the results). Never mix several things in one belief.
- "feeling" must be 1 or 2 lowercase words.
- "intention" must be exactly one of: buy again, stop buying, undecided.

Reply with JSON only, in exactly this format:
{{"hypotheses": [
  {{"belief": "short sentence", "feeling": "one or two words", "intention": "buy again, stop buying, or undecided"}},
  {{"belief": "short sentence", "feeling": "one or two words", "intention": "buy again, stop buying, or undecided"}}
]}}'''
    return ask_llama(prompt)


# ---------------------------------------------------------------
# Agent 2: Domain (check each guess, one at a time)
# ---------------------------------------------------------------
def domain_agent(review, guesses, product_info, brand_context, topics_text=DEFAULT_TOPICS):
    topics = parse_topics(topics_text)
    topic_names = ", ".join(topics.keys())
    topic_help = "\n".join(f'- "{name}" = {definition}' for name, definition in topics.items())
    example_topic = list(topics.keys())[0]      # the first topic, used in the example
    results = []

    for number, guess in enumerate(guesses["hypotheses"], start=1):
        prompt = f'''You check one guess about a customer.
Product: {product_info}
Brand context: {brand_context}
Customer review: "{review[:500]}"
Guess: the customer believes "{guess["belief"]}" and will "{guess["intention"]}".

Question 1: Do the customer's own words support this belief? Answer yes or no.
Question 2: Does the intention clearly CONTRADICT something the customer says? Answer yes or no.
(Answer yes only if the customer says something that goes against the intention, for example the customer says they will return the product but the intention is "undecided". If the customer does not mention their plans, answer no.)
Evidence: copy the customer's exact words that support the belief. Write "none" if there are none.
Topic: the main topic of THIS belief. Choose exactly one of: {topic_names}.
{topic_help}
Valence: is this belief a "problem" the customer has, "praise" (the customer is happy about it), or "mixed"? Answer exactly one of: problem, praise, mixed.

Example:
Review: "It is fine overall, but the {example_topic} was a problem for me."
Guess: the customer believes "The {example_topic} is a problem" and will "stop buying".
Answer: {{{{"belief_supported": "yes", "intention_contradicts": "no", "evidence": "the {example_topic} was a problem for me", "topic": "{example_topic}", "valence": "problem"}}}}

Now answer for the guess above. Reply with JSON only, in exactly this format:
{{"belief_supported": "yes or no", "intention_contradicts": "yes or no", "evidence": "words from the review", "topic": "{topic_names}", "valence": "problem, praise, or mixed"}}'''

        answer = ask_llama(prompt)

        # Plain Python decides: keep if the belief is supported AND nothing contradicts the intention
        belief_ok = str(answer.get("belief_supported", "no")).lower() == "yes"
        contradiction = str(answer.get("intention_contradicts", "yes")).lower() == "yes"
        if str(answer.get("topic", "other")).strip().lower() not in topics:
            answer["topic"] = "other"          # the model invented a topic: use "other"
        else:
            answer["topic"] = str(answer["topic"]).strip().lower()
        valence = str(answer.get("valence", "problem")).strip().lower()
        answer["valence"] = valence if valence in ("problem", "praise", "mixed") else "problem"
        # A guess with no words from the customer to back it up is invented, so it is dropped
        evidence_ok = str(answer.get("evidence", "none")).strip().lower() not in ("", "none", "n/a")
        answer["verdict"] = "keep" if (belief_ok and not contradiction and evidence_ok) else "drop"
        answer["hypothesis"] = number
        results.append(answer)

    return {"checked": results}


# ---------------------------------------------------------------
# Run agents 1 and 2 on a single review
# ---------------------------------------------------------------
def analyse_review(review, product_info, brand_context, topics_text=DEFAULT_TOPICS):
    guesses = theory_of_mind(review, product_info)
    checked = domain_agent(review, guesses, product_info, brand_context, topics_text)

    # Keep only the guesses that passed the check
    kept = []
    for guess, item in zip(guesses["hypotheses"], checked["checked"]):
        if item["verdict"] == "keep":
            kept.append({
                "belief": guess["belief"],
                "feeling": guess["feeling"],
                "intention": guess["intention"],
                "topic": item.get("topic", "other"),
                "evidence": item.get("evidence", ""),
                "valence": item.get("valence", "problem"),
            })

    # If nothing survived, flag the review for a human
    return {"review": review, "kept": kept, "needs_human_review": len(kept) == 0}


# ---------------------------------------------------------------
# Agent 3: Prioritiser (counting and ranking, no AI)
# ---------------------------------------------------------------
def make_priority_table(results):
    total = len(results)

    # Find every topic that appears
    all_topics = set()
    for r in results:
        for item in r["kept"]:
            all_topics.add(item["topic"])

    rows = []
    for topic in all_topics:
        reviews_with_topic = 0   # how many reviews mention this topic
        guesses = 0              # how many kept guesses are about this topic
        stop_buying = 0          # how many of those say "stop buying"
        buy_again = 0            # how many say "buy again"
        examples = []            # a few example beliefs (problems and mixed feelings only)
        quotes = []              # a few of the customers' own words (same)
        complaint_reviews = 0    # reviews with a problem or mixed feeling about this topic

        for r in results:
            items = [item for item in r["kept"] if item["topic"] == topic]
            if len(items) > 0:
                reviews_with_topic += 1
            if any(item.get("valence", "problem") != "praise" for item in items):
                complaint_reviews += 1
            for item in items:
                guesses += 1
                if item["intention"] == "stop buying":
                    stop_buying += 1
                if item["intention"] == "buy again":
                    buy_again += 1
                if item.get("valence", "problem") == "praise":
                    continue          # praise is not something to fix
                if len(examples) < 3 and item["belief"] not in examples:
                    examples.append(item["belief"])
                quote = str(item.get("evidence", "")).strip()[:150]
                if len(quotes) < 3 and quote.lower() not in ("", "none") and quote not in quotes:
                    quotes.append(quote)

        share = reviews_with_topic / total
        decided = stop_buying + buy_again      # guesses where the customer's plan is clear

        # Priority: how many reviews mention the topic
        if share >= 0.25:
            priority = "High"
        elif share >= 0.10:
            priority = "Medium"
        else:
            priority = "Low"

        # Risk: among the guesses with a clear plan, how many say "stop buying".
        # "undecided" says nothing about risk, so it is left out. Fewer than 3 clear guesses = not enough signal.
        if decided < 3:
            risk = "Unclear"
        elif stop_buying / decided >= 0.5:
            risk = "High"
        elif stop_buying / decided >= 0.25:
            risk = "Medium"
        else:
            risk = "Low"

        rows.append({
            "topic": topic,
            "reviews": reviews_with_topic,
            "share_%": round(share * 100),
            "priority": priority,
            "risk_of_losing_customer": risk,
            "decided": decided,
            "complaints": complaint_reviews,
            "examples": examples,
            "quotes": quotes,
        })

    columns = ["topic", "reviews", "share_%", "priority", "risk_of_losing_customer", "decided", "complaints", "examples", "quotes"]
    if len(rows) == 0:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).sort_values("reviews", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------
# Writing the advice, then Agent 4: Validation
# ---------------------------------------------------------------
def write_action(topic, examples, product_info, brand_context, quotes=None,
                 topic_definition="", feedback="", others=""):
    quotes = quotes or []
    retry = f"\nYour previous advice was rejected: {feedback}\nWrite a different, better action.\n" if feedback else ""
    prompt = f'''You advise a brand manager.
Product: {product_info}
Brand context: {brand_context}
Topic: {topic} ({topic_definition})
What customers believe (some may be about other topics, ignore those):
{json.dumps(examples)}
What customers actually wrote:
{json.dumps(quotes)}
Other complaints about this product (your advice must NOT make these worse): {others or "none"}
{retry}
Write two short sentences, ONLY about the topic "{topic}":
- mindset: what customers believe about "{topic}", and what went wrong or what they expected, in plain words. Do not talk about other topics.
- action: one concrete change to the PRODUCT ITSELF that fixes the problem. It must change the formula, texture, scent, packaging, size, applicator, price or product range.
  Good examples: "Offer a lighter, gel-cream version of the formula." or "Replace the plastic hinge with a metal hinge."
  Do NOT name ingredients, sizes, numbers or packaging parts unless they appear in what customers wrote or in the brand context. Describe the change in general words (for example "a gentler formula", "a bigger size").
  NOT allowed: photo galleries, progress trackers, guides, warning labels, website content, marketing, testimonials, trust or transparency.

Reply with JSON only, in exactly this format:
{{"mindset": "one sentence", "action": "one sentence"}}'''
    return ask_llama(prompt)


def validate_action(topic, mindset, action, topic_definition="", others=""):
    prompt = f'''You check advice given to a brand manager.
Topic: {topic} ({topic_definition})
What customers believe: {mindset}
Advice: {action}

Question 1: Is the advice about the topic "{topic}" and not about a different topic (for example scent or packaging advice under "hydration" is no)? Answer yes or no.
Question 2: Does the advice name a specific thing to change, build or write? Answer no if it is vague (for example "improve quality", "increase transparency", "build trust"). Answer yes or no.
Question 3: Does the advice change the product itself (formula, texture, scent, packaging, size, applicator, price, product range)? Answer no if it only adds information or marketing (a gallery, tracker, guide, warning label, website text, campaign). Answer yes or no.
Question 4: Could the advice make one of these other customer complaints worse: {others or "none"}? (For example a stronger active ingredient can worsen irritation, a richer formula can worsen a greasy feel.) Answer yes or no.
Comment: one short sentence explaining your answers.

Example:
Topic: durability
What customers believe: The handle breaks after a week.
Advice: Switch the handle to a stronger plastic and test it before shipping.
Answer: {{"addresses_topic": "yes", "specific_and_doable": "yes", "changes_product": "yes", "makes_other_worse": "no", "comment": "The advice targets the weak handle and is concrete."}}

Example:
Topic: results
What customers believe: The cream does not give the promised results.
Advice: Add a before-and-after photo gallery to the product page.
Answer: {{"addresses_topic": "yes", "specific_and_doable": "yes", "changes_product": "no", "makes_other_worse": "no", "comment": "A gallery is marketing and does not change the product."}}

Now answer for the advice above. Reply with JSON only, in exactly this format:
{{"addresses_topic": "yes or no", "specific_and_doable": "yes or no", "changes_product": "yes or no", "makes_other_worse": "yes or no", "comment": "one short sentence"}}'''
    return ask_llama(prompt)


_INGREDIENTS = ["retinol", "peptide", "caffeine", "niacinamide", "vitamin", "aloe", "green tea", "hyaluronic",
                "ceramide", "collagen", "squalane", "glycerin", "salicylic", "glycolic", "shea", "centella",
                "chamomile", "antioxidant", "humectant", "emollient", "spf", "sunscreen", "oil-free"]
_PARTS = ["jar", "pump", "tube", "bottle", "dropper", "spatula", "airless", "lid", "applicator", "sachet"]
_NUMBER = re.compile(r"\d+(?:\.\d+)?\s?-?\s?(?:%|(?:ml|g|oz|hours?|hrs?|h|weeks?|days?|months?|x)\b)")


def _ungrounded(text, allowed):
    """Return the invented details in `text`: numbers with units, ingredients or packaging parts
    that appear neither in the customers' words nor in the product / brand text."""
    text, allowed = text.lower(), allowed.lower()
    squashed = allowed.replace(" ", "").replace("-", "")
    found = []
    for match in _NUMBER.findall(text):
        if match.replace(" ", "").replace("-", "") not in squashed:
            found.append(match.strip())
    for word in _INGREDIENTS + _PARTS:
        if re.search(r"\b" + re.escape(word), text) and word not in allowed:
            found.append(word)
    return sorted(set(found))


_GENERIC = {"effect", "visible", "skin", "feels", "product", "other", "customers", "anything", "fits", "none", "above"}


def _on_topic(action, topic, definition):
    """Plain-Python guard: the advice must use at least one word of its own topic.
    (The small model sometimes says yes to advice about a different topic.)"""
    words = [topic] + [w.strip(",.;:()\"'") for w in definition.lower().split()]
    stems = {w[:5] for w in words if len(w) >= 5 and w not in _GENERIC}
    text = action.lower()
    return any(stem in text for stem in stems)


def _checks_passed(check):
    """Count the passed checks (0 to 5): the validator's 3 yes answers, "does not make another
    complaint worse", and the Python check that no detail was invented."""
    passed = sum(str(check.get(key, "no")).lower() == "yes"
                 for key in ("addresses_topic", "specific_and_doable", "changes_product"))
    passed += str(check.get("makes_other_worse", "no")).lower() != "yes"
    passed += str(check.get("grounded", "yes")).lower() == "yes"
    return passed


def _check_advice(advice, topic, definition, others, allowed):
    """Run the validator and the two plain-Python guards on one piece of advice."""
    check = validate_action(topic, advice["mindset"], advice["action"], definition, others)
    notes = []
    if definition and not _on_topic(advice["action"], topic, definition):
        check["addresses_topic"] = "no"
        notes.append(f"The advice must be about {topic} ({definition}), not about another topic.")
    invented = _ungrounded(advice["mindset"] + " " + advice["action"], allowed)
    if invented:
        check["grounded"] = "no"
        notes.append("Remove details the customers never mentioned: " + ", ".join(invented) + ".")
    if str(check.get("makes_other_worse", "no")).lower() == "yes":
        notes.append("The advice could worsen another complaint (" + others + ").")
    if notes:
        check["comment"] = " ".join(notes)
    return check


def make_briefing(priority_table, product_info, brand_context, how_many=3, topics_text=DEFAULT_TOPICS):
    briefing = []
    topics = parse_topics(topics_text)

    # The biggest real topics (leaving out the catch-all "other"), only where at least 2 reviews
    # describe a problem. One review is not enough, and praise is not something to fix.
    complaints = priority_table["complaints"] if "complaints" in priority_table.columns else priority_table["reviews"]
    actionable = priority_table[(priority_table["topic"] != "other") & (complaints >= 2)].head(how_many)

    for i in actionable.index:
        row = actionable.loc[i]
        topic = row["topic"]
        definition = topics.get(topic, "")
        quotes = list(row["quotes"]) if "quotes" in row.index else []

        # The product's other complaints: the advice must not make them worse
        rest = priority_table[(priority_table["topic"] != topic) & (priority_table["topic"] != "other")]
        rest = rest[(rest["share_%"] >= 20) | (rest["risk_of_losing_customer"] == "High")]
        others = ", ".join(f"{r['topic']} ({r['share_%']}% of reviews)" for _, r in rest.head(3).iterrows())

        # Words the advice may use: the customers' own words and the product / brand text
        allowed = " ".join(quotes) + " " + product_info + " " + brand_context

        advice = write_action(topic, row["examples"], product_info, brand_context, quotes, definition, "", others)
        check = _check_advice(advice, topic, definition, others, allowed)
        if _checks_passed(check) < 5:      # try once more, with the reasons
            retry = write_action(topic, row["examples"], product_info, brand_context, quotes,
                                 definition, check.get("comment", ""), others)
            retry_check = _check_advice(retry, topic, definition, others, allowed)
            if _checks_passed(retry_check) >= _checks_passed(check):
                advice, check = retry, retry_check

        # Confidence is counted by Python
        passed = _checks_passed(check)
        if str(check.get("grounded", "yes")).lower() == "no":
            confidence = "Low"      # the advice still contains a detail the customers never mentioned
        elif passed == 5 and row["share_%"] >= 25:
            confidence = "High"
        elif passed >= 4:
            confidence = "Medium"
        else:
            confidence = "Low"

        briefing.append({
            "topic": topic,
            "priority": row["priority"],
            "risk": row["risk_of_losing_customer"],
            "decided": int(row["decided"]) if "decided" in row.index else None,
            "reviews": int(row["reviews"]),
            "quotes": quotes,
            "mindset": advice["mindset"],
            "action": advice["action"],
            "confidence": confidence,
            "needs_human_review": confidence == "Low",
            "comment": check.get("comment", ""),
        })

    return briefing


# ---------------------------------------------------------------
# The "normal tool" for comparison: plain sentiment labels
# ---------------------------------------------------------------
def baseline_counts(reviews):
    analyzer = SentimentIntensityAnalyzer()
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for text in reviews:
        score = analyzer.polarity_scores(text)["compound"]
        if score >= 0.05:
            counts["positive"] += 1
        elif score <= -0.05:
            counts["negative"] += 1
        else:
            counts["neutral"] += 1
    return counts
