# Illinois Campus Transportation Dashboard

All application logic is in **app.py**. There is no survey.py or external question-definition file. The included original workbook loads automatically from the repository.

## GitHub and Streamlit setup

1. Extract the ZIP and create a GitHub repository, such as `uiuc-campus-transportation`.
2. Upload the project folder's contents to the repository root: `app.py`, `Campus Transportation Survey raw.xlsx`, `thematic_review.csv`, `requirements.txt`, `.streamlit/config.toml`, and `.gitignore`. Include documentation and tests if desired. Keep the workbook filename unchanged.
3. Go to https://share.streamlit.io/ and select **Create app**.
4. Select your repository and branch. Use `app.py` as the main file and Python 3.12 in advanced settings, then deploy.
5. The app opens with the workbook already loaded. Visitors do not need to upload data.

The package has not been pushed or deployed in your accounts. A public repository exposes the full workbook and coding CSV, including contact details in comments. A private repository uses the same loading behavior; viewer access is a separate hosting setting.

Deployment reference: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## Design and story

The UI uses Illini Orange `#FF5F05` and Illini Blue `#13294B`, a navy hero, orange bars, navy headings, and light cards. Color source: https://brand.illinois.edu/visual-identity/color

Eight tabs connect the story and evidence: The story, Who responded, Commute patterns, Barriers & improvements, Safety & accessibility, Thematic analysis, All questions, and Coding review. The landing page follows differences by campus role, transit practicality, active travel, driving constraints, and written experiences. See ANALYSIS.md for the narrative findings.

## Thematic methods and status

The two open-ended questions have 914 responses from 563 distinct workbook rows. Six exploratory interpretive themes are supported by twelve descriptive codes. All responses receive transparent rule-based candidate codes. Fifty-two selected full responses were read in context and coded by AI, marked **AI reviewed**; 862 remain **Suggested**. No records start as Human reviewed.

This is an exploratory AI-assisted synthesis, not a completed human-validated thematic study. Automated suggestions can miss meanings, misread negation, or match praise and neutral mentions. No sentiment score, saturation claim, causal finding, or intercoder reliability is inferred. Frequency is not importance.

The six interpretive narratives summarize the original dataset and are not automatically rewritten when filters change. Code counts, evidence lists, and quantitative charts respond to filters. Curated excerpts display only when the source row is selected and the excerpt matches the source.

Writer counts deduplicate by source row within each code across both questions. Denominators include all selected writers in the coding scope, including uncoded replies. Codes overlap, so percentages can sum above 100%. Question and role comparisons use writers within each respective group. All definitions, exclusions, rules, and planning questions are visible in the codebook expander and editable in app.py.

## Review coding

1. Open Coding review. Filter by prompt, status, or text. Use the full-response selector to read the entire comment.
2. Edit Codes with exact codebook names, separating them with ` | `. Clear Codes to record that none apply.
3. Add a Rationale and mark Human reviewed after reading the response.
4. Download `thematic_review.csv`. Upload it in the sidebar to refresh the charts immediately, or replace it in GitHub to retain the changes for all visitors.

Edits do not write to GitHub automatically. Export preserves records outside the current filters. Comment IDs combine the prompt, cleaned text, and source row, so identical comments by different writers stay separate. Changed text or reordered rows need fresh review. Unknown codes and duplicate IDs are rejected.

The evidence viewer masks emails and common phone formats for display. Raw workbook and coding files remain unaltered. The full comments are available in the review editor.

## Descriptive definitions

- Default: U.S. eligible responses only, 810 of 816 rows. Rows are responses; no person ID exists for deduplication.
- Percentages use respondents answering each question within the filters. Blanks are excluded. Not applicable remains unless the metric explicitly excludes it.
- Multi-select answers split at semicolons, clean whitespace, and count repeated selections once per response.
- Recorded mode categories are retained. Bus uses the exact Bus response. Original campus roles are available in All questions; comparisons group other/multiple roles.
- The story's driving reasons are restricted to primary drive-alone commuters. General question charts include all answers unless filtered.
- Ranking uses the first recorded item only. Lists often include ten modes despite rank-up-to-five wording.
- Numeric responses are not trimmed or imputed. The age label `and older` is retained without an inferred lower bound.
- ZIP codes remain in the raw workbook but are excluded from analytical views.
- Results are unweighted descriptions of respondents, not necessarily the campus population.

## Run locally

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux instead: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Replace the included workbook with the same headings to update the data. The first worksheet is read. Descriptive measures recalculate; qualitative narratives and source excerpts need reassessment for changed data.

## Checks

```bash
python -m unittest discover -s tests -v
```

Checks cover source totals, mode counts, denominators, writer deduplication, exact quote provenance, review validation, and contact masking. Streamlit checks cover rendering, filters, coding scope, topic selection, and empty results.
