# Responsible web access: how Liability Radar collects sources lawfully and politely

> This is our team's design reasoning, not legal advice. Before relying on it beyond a
> university prototype, confirm with the course organisers and, for real use, the bank's legal team.

## The short answer

"Web scraping" isn't illegal in itself. What creates risk is **how** you collect and **what you
do** with the material. We reduce the risk on four fronts:

| Risk | What could go wrong | Our control | Where in code |
|---|---|---|---|
| Unauthorised access | Getting past logins, paywalls, CAPTCHAs or blocks can be an offence (in Singapore, the Computer Misuse Act 1993) | Public pages only; stop at 401/403/429; never retry around a block | `scraping.fetch` |
| Site owner's wishes | Ignoring robots.txt or terms of use: bad faith, IP bans, reputational harm to a bank | robots.txt obeyed (RFC 9309); terms checked when a source is added to the registry | `scraping.robots_check`, `source_registry.py` |
| Copyright | Copying and redistributing whole documents | Copies are used only for analysis; reports quote short excerpts with attribution and links; the cache isn't shared (git-ignored) | `report.py`, `.gitignore` |
| Server load | Hammering a small site | ≥3 s between requests per site (longer if the site's Crawl-delay asks); caching means each page is fetched once | `scraping._wait_politely`, cache |
| Personal data | Collecting people's data without a basis (Singapore: PDPA 2012) | Official regulatory documents only; no social media, forums or victim data; demo cases are fictional | `config.TRUSTED_DOMAINS`, registry |
| AI provider | Sending confidential data to a third-party AI | Only public documents reach the AI; Gemini's free tier may use prompts to improve Google's products, so production would use Bedrock or a paid tier | `llm.py` |

## Our rules, in plain words

1. **Curate first, crawl last.** Most sources come from a reviewed list (`source_registry.py`), not
   from crawling. Discovery search only proposes candidates, and a human must tick them.
2. **Official sites first.** Tier 1 = regulator, government and legislation domains
   (`config.TRUSTED_DOMAINS`). Everything else is labelled secondary and flagged.
3. **Obey robots.txt.** It's checked before every new site. If the site's server is failing or
   unreachable, we assume "not allowed", which is the cautious reading of the standard.
4. **Say who we are.** Our User-Agent names the tool and a contact email. We don't disguise
   ourselves as a browser. (Our earlier prototype did this "to reduce the chance of being
   blocked"; we removed it on purpose, because dodging a block is the opposite of permission.)
5. **Go slowly.** One request per site every 3+ seconds, and never the same page twice (cache).
6. **No break-ins.** No logins, paywalls or CAPTCHAs. If a site refuses (401/403/429), we record it
   and move on.
7. **Keep the evidence, don't redistribute it.** The cache keeps exactly what we read (with a
   SHA-256 fingerprint) for audit, but it stays on the analyst's machine.
8. **Quote, don't copy.** Reports contain short quotes with page numbers and links back to the
   original.
9. **Humans fill the gaps.** If a document can't be fetched (JavaScript download buttons, a
   robots.txt block, or a bank's internal policy), a person downloads or obtains it legitimately
   and adds it to the **library**. The upload records who added it and when.
10. **Log everything.** Every access (read, cached, blocked, refused) is in the run's audit log
    and shown in the app's Audit tab.

## Copyright in Singapore: the computational data analysis exception

Singapore's Copyright Act 2021 (sections 243–244) allows copying a work for **computational data
analysis**, under conditions including that:

- you have **lawful access** to the original (for us: public pages, no circumvention);
- the copy is **used only for that analysis**; and
- you **don't supply the copy to others**, except to verify results or for collaborative research.

Our design follows those conditions: lawful access only, analysis-only use, cache not shared, and
reports that link to the original instead of reproducing it. Other countries' rules differ, so
when in doubt, link and quote briefly.

## Checklist: adding a new website to the registry

- [ ] Is it the official publisher (Tier 1)? If not, mark it as secondary (section B).
- [ ] Read the site's terms of use. Note anything about automated access in the registry entry.
      If automated access is prohibited, **download it manually and add it to the library instead**.
- [ ] Check `https://<site>/robots.txt`. The tool enforces it anyway, but know in advance.
- [ ] Is there an official feed (RSS, API, download page)? Prefer it over page scraping.
- [ ] Does the page contain personal data? If so, don't add it.

## What a bank would do in production

- Use **licensed data feeds** (legal and news databases) through their own MCP servers. The MCP
  design means the agents don't change.
- Use regulators' **official feeds and APIs** where offered.
- Run the AI inside the bank's own cloud account (e.g. Amazon Bedrock).
- Have the legal team approve the source registry and its terms-of-use notes.
