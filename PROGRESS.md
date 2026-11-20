# Progress (21 Oct 2026)

## Done and live on `main`
- **Pricing by type of student, with a launch offer** (commit `c7f4ce3`):
  - Regular prices: JEE/NEET ₹359, College ₹299, School ₹249 a month.
  - Launch offer for the first 200 paid students: JEE/NEET ₹249, College ₹199, School ₹149.
  - Each student's AI limit equals what their pass brings in, so no student costs more than they paid.
- **School syllabus, Class 1 to 12, matched to NCERT.**
  - `backend/app/data/syllabus/school/class_01.json` to `class_12.json`: 12 classes, 1,087 chapters, about 5,600 topics.
    Built by `tools/school_syllabus/build_school.py`.
  - Chapter names come from each NCERT book's contents page (2026-27 reprints). Classes 9 to 12 follow the CBSE
    2026-27 curriculum (its marks become each chapter's weightage; chapters CBSE dropped are left out).
  - Topics are the section headings of NCERT's own chapter PDFs (`tools/school_syllabus/heads_all.py` reads them
    block by block, so wrapped headings come back whole and the Class 10 books' shadowed headings read cleanly),
    CBSE's content list for Class 11-12 science, or written by hand where a book's headings can't be read
    (`school_topics.py`, which also holds a short list of fixes for stray lines).
  - Sign-up for Class 1 to 12, subjects to pick, plans in book order, board dates for Class 10 and 12, chapter tests
    written for the class (the chapter's NCERT topics, the age, rupees, English or Hindi/Sanskrit).
  - Checked in the browser as a Class 5, a Class 10 and a Class 11 commerce student.

- **New B.Tech branches:** AI & Data Science / AI-ML (`college_ai`), Chemical (`college_che`) and Biotechnology
  (`college_bt`), each with a typical AICTE-model 8-semester plan; 43 new library courses in `ai_data.json`,
  `chemical.json` and `biotech.json` (shared courses, such as Chemical Process Calculations, are one course).
  Checked in the browser for all three.

- **GGSIPU and AKTU semester plans,** read from the universities' own documents:
  - GGSIPU: the USICT handbook for affiliated institutes (batches from 2021-22) for CSE, IT, ECE, EE, ME, CE and
    AI (CSE-AIML). Chemical and Biotech are not offered at its affiliated colleges, so they use the typical plan.
    Semester 8 there is the project or internship: the app keeps semester 7's courses until the student picks.
  - AKTU: the 2nd-year (2023-24), 3rd-year (2024-25) and 4th-year (2025-26) schemes in force, and the 2026-27
    stream first year, for all nine branches. Electives are filled with a common choice from AKTU's own lists.

## Next
1. **The full go-live check,** login to the end: every page and feature, as each type of student; fix and polish.

## Good to know
- Rebuild the school data with `backend\.venv\Scripts\python -I tools\school_syllabus\build_school.py`. To re-read
  NCERT headings, run `heads_all.py <folder> <list of chapters>` into a scratch folder and compare before copying.
- `backend/tests/test_gate_boards.py` checks every class for cut-off or garbled topics, so a bad rebuild fails tests.
- NCERT's website sometimes drops downloads; the tools retry on their own.
