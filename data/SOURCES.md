# Setswana data sources

Raw downloads live in `data/raw/` (gitignored — re-download from the URLs below).
Downloaded 2026-10-01.

## Recommended core (what the learning app should be built on)

| Role in app | Source | Folder | Size | License |
|---|---|---|---|---|
| **Course structure + audio** (lessons, dialogues, grammar order) | Peace Corps Botswana *Introduction to the Setswana Language* — lesson PDF + 25 MP3s + *There is no word for grammar in Setswana* | `peace_corps/` | 23 lessons, ~41 MB audio | US Gov work — public domain |
| **Deep course / drills** | Mistry, *An Introduction to Spoken Setswana* (ERIC ED283381, 1987) — 163 lessons, vocab lists, exercises | `archive_org/mistry_1987_*` | PDF + OCR text | Public domain mark |
| **Grammar reference** | Peace Corps Language Handbook Series (1979): Grammar, Special Skills, Communication & Culture | `archive_org/peacecorps_1979_*` | 3 PDFs + OCR text | US Gov work — public domain |
| **Big bilingual dictionary** | J. Tom Brown, *Secwana Dictionary* (Secwana↔English) | `archive_org/brown_1885_*` | ~1.9 MB clean OCR text | Public domain (pre-1930). **Old orthography** (c→tsh, é/ô marks) — must be normalised |
| **Modern lexicon with English meaning** | African Wordnet: Setswana 1.0 (SADiLaR) — 12,182 lemmas linked to Princeton WordNet 2.0 synset IDs | `sadilar/african_wordnet/` | LMF XML | CC BY 4.0 |
| English glosses for the wordnet | Princeton WordNet 2.0 `dict/` (join on `ENG20-<offset>-<pos>`) | `princeton_wordnet_2.0/` | | WordNet license (permissive) |
| **Word frequency** (what to teach first) + modern corpus | NCHLT Setswana Text Corpora (SADiLaR) — frequency list (12,406 types), named-entity list, ~7 MB clean corpus | `sadilar/nchlt_text/` | | CC BY 2.5 ZA |
| **Example sentences, EN↔TN** | MAFAND-MT en-tsn (news) | `mafand/` | 4,942 pairs | CC BY-NC 4.0 (non-commercial) |
| Example sentences, EN↔TN | FLORES-200 `tsn_Latn` / `eng_Latn` (Wikipedia-style) | `flores200/` | 2,009 pairs | CC BY-SA 4.0 |
| Example sentences, everyday | Tatoeba `tsn` + links to English | `tatoeba/` | 42 sentences | CC BY 2.0 FR |
| IPA, tones, noun-class prefixes for a few common words | English Wiktionary `Category:Tswana lemmas` — Tswana section wikitext per page (fetched via MediaWiki API) | `wiktionary/` | 350 lemmas | CC BY-SA 4.0 |
| Classic reader (texts + translations) | Jones & Plaatje, *A Sechuana Reader* (1916) | `archive_org/jones_plaatje_*` | | Public domain. IPA orthography |

## URLs

- Peace Corps: https://files.peacecorps.gov/multimedia/audio/languagelessons/botswana/Bw_Setswana_Language_Lessons.pdf
  audio mirror: `https://fsi-language-courses-media.nyc3.cdn.digitaloceanspaces.com/languages-peacecorps/Setswana/Setswana_Lesson_<n>.mp3`
- Internet Archive (`https://archive.org/details/<id>`):
  `secwanadictionar00brow`, `AnIntroductionToSpokenSetswanaED283381`,
  `micro_IA41153606_0098` (grammar), `micro_IA41153606_0099` (special skills),
  `micro_IA41153606_0100` (communication & culture), `sechuanareaderin00joneuoft`
- African Wordnet Setswana: https://repo.sadilar.org/handle/20.500.12185/390
- NCHLT Setswana Text Corpora: https://repo.sadilar.org/handle/20.500.12185/343
- Princeton WordNet 2.0: https://wordnetcode.princeton.edu/2.0/WordNet-2.0.tar.gz
- MAFAND-MT: https://github.com/masakhane-io/lafand-mt/tree/main/data/text_files/en-tsn
- FLORES-200: https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz
- Tatoeba: https://downloads.tatoeba.org/exports/per_language/tsn/
- Wiktionary: https://en.wiktionary.org/wiki/Category:Tswana_lemmas (API: `list=categorymembers` + `prop=revisions`). The kaikki.org full dump (3 GB) was too slow to fetch and has no Tswana-only file.

## Deliberately not downloaded

- **sadictionaries.co.za / setswana.co.za, Glosbe** — copyrighted, scrape-only, no bulk licence.
- **Oxford Bilingual School Dictionary** — copyrighted.
- **NCHLT Setswana speech corpus** (SADiLaR, many GB) — useful later for pronunciation audio/TTS, not needed for v1.
- **Autshumato / PuoData / Marothodi** — large government/web corpora; good for NLP, overkill for a learner app.
