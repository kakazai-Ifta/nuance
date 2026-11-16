"""
agents.py - the brain of Nuance.

It contains the four agents plus the ranking step:
  1. Theory-of-Mind agent : guesses what each customer believes, feels and intends
  2. Domain agent         : checks each guess against the review and the brand context
  3. Prioritiser          : counts and ranks the topics (plain Python)
  4. Validation agent     : checks the advice and gives a confidence level
"""

import json
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

Example:
Review: "It is fine overall, but the {example_topic} was a problem for me."
Guess: the customer believes "The {example_topic} is a problem" and will "stop buying".
Answer: {{{{"belief_supported": "yes", "intention_contradicts": "no", "evidence": "the {example_topic} was a problem for me", "topic": "{example_topic}"}}}}

Now answer for the guess above. Reply with JSON only, in exactly this format:
{{"belief_supported": "yes or no", "intention_contradicts": "yes or no", "evidence": "words from the review", "topic": "{topic_names}"}}'''

        answer = ask_llama(prompt)

        # Plain Python decides: keep if the belief is supported AND nothing contradicts the intention
        belief_ok = str(answer.get("belief_supported", "no")).lower() == "yes"
        contradiction = str(answer.get("intention_contradicts", "yes")).lower() == "yes"
        if str(answer.get("topic", "other")).strip().lower() not in topics:
            answer["topic"] = "other"          # the model invented a topic: use "other"
        else:
            answer["topic"] = str(answer["topic"]).strip().lower()
        answer["verdict"] = "keep" if (belief_ok and not contradiction) else "drop"
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
        examples = []            # a few example beliefs
        quotes = []              # a few of the customers' own words

        for r in results:
            items = [item for item in r["kept"] if item["topic"] == topic]
            if len(items) > 0:
                reviews_with_topic += 1
            for item in items:
                guesses += 1
                if item["intention"] == "stop buying":
                    stop_buying += 1
                if len(examples) < 3:
                    examples.append(item["belief"])
                quote = str(item.get("evidence", "")).strip()
                if len(quotes) < 3 and quote != "" and quote.lower() != "none":
                    quotes.append(quote[:150])

        share = reviews_with_topic / total
        stop_share = stop_buying / guesses

        # Priority: how many reviews mention the topic
        if share >= 0.25:
            priority = "High"
        elif share >= 0.10:
            priority = "Medium"
        else:
            priority = "Low"

        # Risk: how many guesses say "stop buying"
        if stop_share >= 0.5:
            risk = "High"
        elif stop_share >= 0.25:
            risk = "Medium"
        else:
            risk = "Low"

        rows.append({
            "topic": topic,
            "reviews": reviews_with_topic,
            "share_%": round(share * 100),
            "priority": priority,
            "risk_of_losing_customer": risk,
            "examples": examples,
            "quotes": quotes,
        })

    columns = ["topic", "reviews", "share_%", "priority", "risk_of_losing_customer", "examples", "quotes"]
    if len(rows) == 0:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).sort_values("reviews", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------
# Writing the advice, then Agent 4: Validation
# ---------------------------------------------------------------
def write_action(topic, examples, product_info, brand_context, quotes=None):
    quotes = quotes or []
    prompt = f'''You advise a brand manager.
Product: {product_info}
Brand context: {brand_context}
Topic: {topic}
What customers believe about this topic:
{json.dumps(examples)}
What customers actually wrote:
{json.dumps(quotes)}

Write two short sentences:
- mindset: what customers with this topic believe, and what went wrong or what they expected, in plain words.
- action: one concrete change that fixes the problem customers describe. Name the specific thing to change, build or write.
  Good examples: "Add a 4-week results guide to the product page." or "Replace the plastic hinge with a metal hinge."
  Do not answer with only marketing, testimonials, trust or transparency.

Reply with JSON only, in exactly this format:
{{"mindset": "one sentence", "action": "one sentence"}}'''
    return ask_llama(prompt)


def validate_action(topic, mindset, action):
    prompt = f'''You check advice given to a brand manager.
Topic: {topic}
What customers believe: {mindset}
Advice: {action}

Question 1: Does the advice directly address the topic "{topic}"? Answer yes or no.
Question 2: Does the advice name a specific thing to change, build or write, which fixes the problem customers describe? Answer no if it is vague (for example "improve quality", "increase transparency", "build trust") or only promotes the product (a marketing campaign, testimonials). Answer yes or no.
Comment: one short sentence explaining your answers.

Example:
Topic: durability
What customers believe: The handle breaks after a week.
Advice: Switch the handle to a stronger plastic and test it before shipping.
Answer: {{"addresses_topic": "yes", "specific_and_doable": "yes", "comment": "The advice targets the weak handle and is concrete."}}

Example:
Topic: results
What customers believe: The cream does not give the promised results.
Advice: Increase transparency to build trust.
Answer: {{"addresses_topic": "yes", "specific_and_doable": "no", "comment": "The advice is vague and names no concrete change."}}

Now answer for the advice above. Reply with JSON only, in exactly this format:
{{"addresses_topic": "yes or no", "specific_and_doable": "yes or no", "comment": "one short sentence"}}'''
    return ask_llama(prompt)


def make_briefing(priority_table, product_info, brand_context, how_many=3):
    briefing = []

    # The biggest real topics (leaving out the catch-all "other")
    actionable = priority_table[priority_table["topic"] != "other"].head(how_many)

    for i in actionable.index:
        row = actionable.loc[i]

        quotes = list(row["quotes"]) if "quotes" in row.index else []
        advice = write_action(row["topic"], row["examples"], product_info, brand_context, quotes)
        check = validate_action(row["topic"], advice["mindset"], advice["action"])

        # Python counts the confidence points
        score = 0
        if str(check.get("addresses_topic", "no")).lower() == "yes":
            score += 1
        if str(check.get("specific_and_doable", "no")).lower() == "yes":
            score += 1
        if row["share_%"] >= 25:      # many reviews support this topic
            score += 1

        if score == 3:
            confidence = "High"
        elif score == 2:
            confidence = "Medium"
        else:
            confidence = "Low"

        briefing.append({
            "topic": row["topic"],
            "priority": row["priority"],
            "risk": row["risk_of_losing_customer"],
            "reviews": int(row["reviews"]),
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
