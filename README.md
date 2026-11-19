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

### 1. Data Sources

Nuance uses the **Sephora Products and Skincare Reviews** dataset, available on Kaggle. The data consists of customer reviews and product metadata, including:

- Customer review text
- Star ratings (1–5)
- Product and brand identifiers
- Product names and related metadata

The dataset enables the analysis of customer satisfaction, product-specific concerns, and recurring patterns in consumer feedback.

**Source:** [Sephora Products and Skincare Reviews](https://www.kaggle.com/datasets/nadyinky/sephora-products-and-skincare-reviews)

The full dataset is not included in this repository due to its size.

### 2. Data Preparation and Cleaning

The data preprocessing pipeline involved the following steps:

1. **Data consolidation:** Combined five customer review CSV files into a single dataset.
2. **Metadata integration:** Merged the review data with product metadata using product identifiers.
3. **Missing-value treatment:** Identified and removed observations with missing review text.
4. **Exploratory analysis:** Examined rating distributions and product-level review counts.
5. **Sample preparation:** Created smaller datasets for product-level analysis and model evaluation.

#### Dataset Summary

| Processing Stage | Number of Reviews |
|---|---:|
| Original combined dataset | 1,094,411 |
| Reviews removed due to missing text | 1,444 |
| Final cleaned dataset | 1,092,967 |

The cleaning process retained approximately **99.87%** of the original reviews.

### 3. Exploratory Data Analysis (EDA)

Exploratory Data Analysis was conducted to investigate customer rating patterns and understand the limitations of using numerical ratings as the sole measure of customer satisfaction.

#### Overall Rating Distribution

| Rating Category | Percentage |
|---|---:|
| Positive (4–5 stars) | 82.08% |
| Mid-range (3 stars) | 7.48% |
| Negative (1–2 stars) | 10.44% |

The distribution is heavily skewed toward positive ratings, with more than 82% of reviews receiving four or five stars.

However, star ratings do not necessarily capture the complexity of customer experiences. A single review may express satisfaction with certain product attributes while highlighting dissatisfaction with others.

For example, a customer may appreciate a moisturizer's lightweight texture but express concerns about its hydration performance or price.

This motivates Nuance's approach of analysing **individual product attributes, mixed opinions, and underlying customer expectations**, rather than relying exclusively on aggregate star ratings.

**Note:** These categories are based on numerical star ratings and should not be interpreted as independently validated text sentiment labels.

### 4. Product-Level Case Study

A subset of **9,080 reviews across five skincare products** was selected for further analysis.

#### Selected Products

| Brand | Product | Number of Reviews |
|---|---|---:|
| Dior | Capture Totale Firming & Wrinkle-Correcting Cream | 654 |
| Dior | Capture Totale Super Potent Eye Serum | 1,092 |
| Dior | Capture Totale Super Potent Rich Cream | 678 |
| Dior | Cica Recover & Repair Multi-Use Balm | 611 |
| Drunk Elephant | Protini Polypeptide Firming Refillable Moisturizer | 6,045 |
| **Total** | | **9,080** |

The selected products allow us to investigate differences in customer satisfaction and identify recurring product-level concerns.

The deployed Nuance demo focuses on a smaller sample of Dior reviews and uses precomputed analysis results.

### 5. Evaluation Dataset

A **stratified diagnostic sample of 100 customer reviews** was constructed to evaluate Nuance's ability to interpret customer feedback across different rating categories.

The sample includes 20 reviews from each of the five selected products.

#### Sampling Strategy

| Rating Category | Reviews per Product | Total Reviews |
|---|---:|---:|
| Negative (1–2 stars) | 4 | 20 |
| Mid-range (3 stars) | 10 | 50 |
| Positive (4–5 stars) | 6 | 30 |
| **Total** | **20** | **100** |

Three-star reviews were deliberately oversampled because they are particularly useful for investigating mixed customer opinions and identifying product attributes that numerical ratings may obscure.

The evaluation sample is intended to assess whether Nuance can:

- Identify relevant product topics and attributes.
- Distinguish customer praise from complaints.
- Recognise mixed sentiment within individual reviews.
- Interpret customer expectations and stated intentions.
- Generate recommendations supported by customer review evidence.

This is a diagnostic sample rather than a statistically representative sample of the full dataset.

AI-assisted reference annotations, where used, should be treated as provisional labels until independently verified. Quantitative performance metrics require comparison between Nuance outputs and matched reference annotations.

### 6. Data Reproducibility

The original Sephora dataset exceeds GitHub's standard file size limit and is therefore not included in the repository.

To reproduce the data preparation process:

1. Download the original Sephora review and product metadata files from Kaggle.
2. Combine the five review CSV files.
3. Merge the combined reviews with product metadata using product identifiers.
4. Remove observations with missing review text.
5. Examine rating distributions and product-level review counts.
6. Select the relevant products and construct the stratified evaluation sample.

The repository includes smaller demonstration files:

- `sample_reviews.csv`: A sample of 40 three-star Dior reviews used for local testing.
- `demo/dior_demo.json`: Precomputed results used by the deployed Streamlit demonstration.

The full preprocessing and exploratory analysis notebooks should be provided alongside the repository if complete reproducibility is required.


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
