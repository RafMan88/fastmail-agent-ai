# FastmailProject

Pipeline to fetch emails from FastMail via JMAP, analyze them with Claude AI, deduplicate interviews, and export results to Excel.

## Setup

1. Create `.env` file with:
FASTMAIL_TOKEN=your_fastmail_token
CLAUDE_API_KEY=your_claude_api_key
FILTER_EMAILS="mail1@fastmail.com, mail2@d2.com"

2. Install dependencies:
pip install -r requirements.txt

3. run
python main.py --mode applications|interviews
interviews: will generate a file of interviews you had in the last x days (date, company, ..etc)
applications: will generate a file of all feedback (positive or not) you had from your applications (date, comment, phone ..etc)

4. Output will be saved in `data/filename.xlsx`.


