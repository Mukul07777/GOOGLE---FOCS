# Learning study: does Focs help students learn from a lecture?

This is a small, honest study you can run in one afternoon plus ten minutes the next day. Its result is one
number, with its uncertainty and its limitations stated beside it. It is a pilot, not proof: say so in the pitch.

## Design

- **Participants:** 12–20 students who haven't studied the topic yet (for example, Class 11 students before the chapter is taught).
- **Groups:** assign students alternately as they arrive (Focs, control, Focs, …), or by coin toss. Don't let them choose, and don't hand-pick.
- **Lecture:** one openly licensed lecture of about 15 minutes, in Hinglish (NPTEL has some). Everyone watches the same video, on the same day, in similar rooms.
  - **Focs group:** watches with Focs live: notes, captions in their language, pop quizzes, and "I'm lost" if it is a room.
  - **Control group:** watches the same video and takes notes on paper, as usual.
- **Test:** the same 6 questions for everyone, straight after the lecture (10 minutes) and again the next day (10 minutes). No notes and no app during either test.
- **Score:** 1 point per question, out of 6. Mark the tests without seeing the group: cover the names and shuffle the papers.

## Before you start

- Write the 6 questions before anyone sees Focs's notes on this lecture, so the test can't be bent towards them. Use the template below.
- Get consent (text below). For students under 18, get it from a parent or guardian too.
- Collect no names in the results file, only `P01`, `P02` and so on. Keep the name-to-code list on paper, and destroy it after the next-day test.

### Consent text (read it out, and get a signature or a recorded "yes")

> We're testing whether a study app helps students learn from a video lecture. You'll watch a 15-minute lecture,
> with or without the app, then answer 6 questions now and 6 tomorrow. It isn't graded and doesn't count anywhere.
> Your answers are recorded under a code, never your name. You can stop at any time without giving a reason.
> Do you agree to take part?

### Test template (6 questions)

| # | Kind | What it checks |
|---|---|---|
| 1 | Recall | A definition or formula stated in the lecture |
| 2 | Recall | A unit, a sign convention, or a fact on the board |
| 3 | Understanding | Why something is true, or what would change if a condition changed |
| 4 | Understanding | Spotting the mistake in a worked step |
| 5 | Application | A numerical problem like the lecture's example, with new numbers |
| 6 | Application | A question in the style of a previous year's paper, on the same idea |

Use one correct answer per question: multiple choice, or a single number. That keeps the marking objective.

## Recording results

Copy [study_results_template.csv](study_results_template.csv) to `study_results.csv`. Add one row per student:

```
participant,group,immediate,next_day,notes
P01,focs,5,4,
P02,control,3,2,
P03,focs,4,,missed day 2
```

## Analysis

```
cd backend
.venv\Scripts\python scripts\study_report.py ..\docs\evidence\study_results.csv
```

The script prints a table to paste as it is. For the test right after the lecture and for the next day, it shows:
- each group's mean and spread;
- the difference between the groups, with a 95% interval;
- the effect size (Cohen's d);
- the study's limitations, worked out from your data.

**If the interval includes 0, the study can't tell the groups apart. Report that too.** A null result honestly
reported is worth more to a judge than a big claim with no interval.

## Limitations to state (the script adds those specific to your data)

- Small sample, one lecture, one topic, a short test.
- Students knew their group; the Focs group may have been more engaged by novelty alone.
- The next-day test measures one day of retention, not exam performance.
