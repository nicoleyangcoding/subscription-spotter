# subscription-spotter

Find the recurring charges hiding in your bank statement, without giving anyone your bank login.

Export your transactions as a CSV file, run one command, and see every subscription, what it costs per year, and which ones quietly went up in price. Everything runs on your computer. Nothing is uploaded.

```
$ subspot examples/sample-statement.csv
Read 257 transactions from 2025-10-01 to 2026-09-29.

MERCHANT            EVERY     AMOUNT    PER YEAR  LAST CHARGE  NOTE
Maple Court Apts    month  $1,850.00  $22,200.00  2026-09-01
City Power & Light  month     $64.20     $770.40  2026-09-18
Pulse Fitness Club  month     $39.00     $468.00  2026-09-14
Streamflix          month     $17.99     $215.88  2026-09-03   price up from $15.49
Newsdaily           year     $129.00     $129.00  2026-09-29   price up from $119.00
Cloudbox Storage    month      $2.99      $35.88  2026-09-09

6 recurring charges, about $23,819.16 per year ($1,984.93 per month).

Possibly cancelled (no recent charge):
MERCHANT      EVERY  AMOUNT  PER YEAR  LAST CHARGE  NOTE
Gamehub Plus  month   $9.99   $119.88  2026-05-21

Price increases: Streamflix, Newsdaily.
```

## Quick start

Requires Python 3.9 or newer.

```bash
pipx install git+https://github.com/nicoleyangcoding/subscription-spotter
subspot transactions.csv
```

To try it before using your own data, run it on the made-up statement in [examples/sample-statement.csv](examples/sample-statement.csv).

## Getting a CSV from your bank

Most banks and card providers offer this in online banking, usually under **Statements**, **Activity** or **Download transactions**. Choose **CSV** (sometimes called "spreadsheet" or "Excel CSV"). Export at least 3 months, and ideally 12, so yearly charges show up too.

`subspot` works out the date, description and amount columns on its own. It also handles:

- separate "money in" and "money out" columns
- spending shown as negative numbers (bank accounts) or positive numbers (most credit cards)
- US (`01/31/2026`), European (`31.01.2026`) and ISO (`2026-01-31`) dates
- `1,234.56` and `1.234,56` amounts, and `;` or tab separators
- account details printed above the header row

You can pass several files at once, for example a checking account and a credit card: `subspot checking.csv card.csv`.

## Options

| Option | What it does |
| --- | --- |
| `--ignore TEXT` | Skip charges whose description contains `TEXT` (repeatable), e.g. `--ignore rent` |
| `--min-amount N` | Ignore charges under `N` |
| `--currency SYMBOL` | Symbol shown before amounts (default `$`) |
| `--format json` / `csv` | Machine-readable output |
| `--dayfirst` | Read ambiguous dates like `03/04/2026` as 3 April |
| `--date-col`, `--desc-col`, `--amount-col` | Name the columns yourself if detection fails |
| `--debit-col`, `--credit-col` | For exports with separate money out and money in columns |
| `--charges-positive` / `--charges-negative` | Say how spending is signed, if the guess is wrong |

## How it decides something is recurring

1. Descriptions are cleaned up, so `SQ *CORNER BAKERY #0412 SEATTLE WA` and `SQ *CORNER BAKERY #0398` count as the same merchant.
2. Charges at one merchant are split by amount, so two different plans at the same store are tracked separately.
3. A group counts as recurring when at least 75% of the gaps between charges match a schedule: weekly, every 2 weeks, monthly, every 3 or 6 months, or yearly. Monthly charges need 3 or more payments, and yearly charges need 2.
4. A charge that hasn't appeared for more than 1.5 cycles is listed as **possibly cancelled**.

Groceries and restaurants rarely show up, because their amounts vary too much. Rent, loans and utilities with fixed bills do show up, because they are recurring charges too. Use `--ignore` to hide them.

## Privacy

- `subspot` makes no network connections, needs no account, and has no dependencies beyond Python itself.
- It only reads the files you pass and prints to your terminal.
- Don't commit real statements to git. This repo's `.gitignore` blocks CSV files outside `examples/`.

## Disclaimer

`subspot` gives estimates based on patterns in your data. It can miss charges or flag something that isn't a subscription. Always check with the merchant or your bank before cancelling anything. This is not financial advice.

## Contributing

Bug reports with a small, anonymized example row are the most helpful. Replace real names and amounts. See [CONTRIBUTING.md](CONTRIBUTING.md) and the [roadmap](ROADMAP.md).

## License

[MIT](LICENSE)
