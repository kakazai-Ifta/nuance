# Nuance

**Reads between the lines of customer reviews, and tells you what to fix first.**

Star ratings and sentiment scores say *how* customers feel. Nuance explains *why*: what customers believe, feel and
intend, which problems matter most, and what the brand could change. Every piece of advice shows its confidence level,
the customers' own words behind it, and waits for a person's decision (Accept, Edit or Reject).

Built for the M2 Quantitative Marketing & Applications course (Topic 3, MetaMind: Reading Between the Lines of Consumer
Feedback). The agent design follows Zhang et al. (2025), *MetaMind*.

## Try it now (nothing to install)
**Live demo: https://nuance.streamlit.app**

Open the link and you are in **Demo mode**: saved results from a real run of Nuance on four Dior skincare products
(Sephora reviews). You can:
- see which products were analysed and how many reviews each has,
- compare a normal sentiment analysis with Nuance's topics,
- read the ranked topics and the advice cards, with confidence levels and the customers' quotes,
- press Accept / Edit / Reject on each card,
- open **How Nuance works** (hover over each box for an example),
- download a **PDF report** or the **JSON results**, for the whole analysis or for one product.

Nothing is computed live in the demo, so there is no AI to set up and no API key.

## How it works
| Step | Agent | What it does | Uses |
|---|---|---|---|
| 1 | Theory-of-Mind | Guesses what the customer believes, feels and intends (two different explanations per review, each about one single thing) | Llama |
| 2 | Domain | Checks each guess against the review and the brand context, finds the topic, and labels it problem, praise or mixed | Llama answers yes/no, Python decides |
| 3 | Prioritiser | Counts how many reviews mention each topic and ranks them. Risk is based only on customers who said clearly whether they would buy again | Python |
| 4 | Validation | Writes advice for each topic with at least 2 problem reviews, checks it, and gives a confidence level | Llama + Python |
| 5 | Human decision | Accept, Edit or Reject | Person |

Design choices:
- A small model gets small tasks (one guess per call, yes/no questions, one worked example per prompt).
- Plain Python makes the decisions: keep or drop, counting, ranking and confidence.
- Praise is never turned into a fix.
- Python checks that advice stays on its topic, does not make another complaint worse, and does not invent details
  (numbers, ingredients, packaging parts) that the customers never mentioned. Advice that fails is rewritten once, then flagged.
- Reviews where no guess survives are flagged for a human.

## Features
- Upload any CSV or TXT file of reviews, with optional filters for rating (3-star only), brand and product.
- Analyses the products with the most reviews (you choose 1 to 5) and shows a bar chart of their review counts.
- Topics are editable. **Suggest topics from my reviews** lets Llama propose them from your data.
- Normal sentiment analysis (VADER) shown next to Nuance's topics.
- Professional **PDF report** with your decisions, for the whole analysis or one product.
- Works for any product category (examples built in: hair diffuser, skincare).

## For developers: analyse your own reviews locally (optional)
Demo mode needs none of this. Live analysis uses **Llama 3.1 8B running locally with Ollama** (no API key, no cloud
account), so it only works on a computer where Ollama is installed. Allow about 10 minutes (mostly the model
download) and 8 GB of RAM or more.

1. Install Ollama from https://ollama.com/download and open it once.
2. Download the model (about 5 GB, once): `ollama pull llama3.1:8b`
3. Get the code and install the packages (Python 3.10 or newer):
   ```
   git clone https://github.com/kakazai-Ifta/nuance.git
   cd nuance
   python3 -m venv venv
   source venv/bin/activate          # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. Start the app: `streamlit run app.py`
5. In the sidebar choose **Analyse my own reviews**, drag in `sample_reviews.csv`, set the text column to `text`, the brand
   column to `brand_name` and the product column to `product_name`, then press **Analyse reviews**.

Speed: about 20 to 30 seconds per review. Use the slider (for example 5 reviews per product) for a quick test.

## Files
- `app.py`: the Streamlit screen.
- `agents.py`: the agents, the checks and the ranking.
- `report.py`: builds the PDF report.
- `sample_reviews.csv`: 40 three-star Dior reviews (10 per product) from the Sephora review dataset, for testing.
- `demo/dior_demo.json`: saved Dior results shown in Demo mode.
- `.streamlit/config.toml`: colour theme.
- `requirements.txt`: Python packages.

## Data
Sephora product and skincare reviews (Kaggle). The full dataset is not included because it is over 100 MB. Any CSV with a
review text column works.

## Limits
- Small local model, and a limited sample (15 reviews per product in the demo, 3-star reviews of one brand), so topic
  shares are indicative.
- A customer's intention (buy again or stop buying) is often not stated, so risk is shown as "Unclear" when fewer than
  3 customers said clearly what they would do.
- Suggested actions are ideas for a human to review. Any detail in them that customers did not write is the AI's
  suggestion, not a finding.
- Treat the output as decision support, not as a verdict: a person approves every recommendation.

## Team
SIMRAT KHALSA 
IFTA KAKAZAI
