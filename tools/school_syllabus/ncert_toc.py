"""Download each chosen NCERT book's prelims (the pages before chapter 1, with its contents) and save the contents
page's text. Run with -I; writes into ncert/ next to this script."""
import pathlib
import subprocess
import sys

import pymupdf

HERE = pathlib.Path(__file__).parent / "ncert"
BOOKS = [
    # class, subject, book, code
    (1, "English", "Mridang", "aemr1"), (1, "Mathematics", "Joyful Mathematics", "aejm1"), (1, "Hindi", "Sarangi", "ahsr1"),
    (2, "English", "Mridang", "bemr1"), (2, "Mathematics", "Joyful Mathematics", "bejm1"), (2, "Hindi", "Sarangi", "bhsr1"),
    (3, "English", "Santoor", "cesa1"), (3, "Mathematics", "Maths Mela", "cemm1"), (3, "Hindi", "Veena", "chve1"),
    (3, "The World Around Us", "Our Wondrous World", "ceev1"),
    (4, "English", "Santoor", "desa1"), (4, "Mathematics", "Maths Mela", "demm1"), (4, "Hindi", "Veena", "dhve1"),
    (4, "The World Around Us", "Our Wondrous World", "deev1"),
    (5, "English", "Santoor", "eesa1"), (5, "Mathematics", "Maths Mela", "eemm1"), (5, "Hindi", "Veena", "ehve1"),
    (5, "The World Around Us", "Our Wondrous World", "eeev1"),
    (6, "English", "Poorvi", "fepr1"), (6, "Mathematics", "Ganita Prakash", "fegp1"), (6, "Hindi", "Malhar", "fhml1"),
    (6, "Sanskrit", "Deepakam", "fsde1"), (6, "Science", "Curiosity", "fecu1"), (6, "Social Science", "Exploring Society: India and Beyond", "fees1"),
    (7, "English", "Poorvi", "gepr1"), (7, "Mathematics", "Ganita Prakash Part I", "gegp1"), (7, "Mathematics", "Ganita Prakash Part II", "gegp2"),
    (7, "Hindi", "Malhar", "ghml1"), (7, "Sanskrit", "Deepakam", "gsde1"), (7, "Science", "Curiosity", "gecu1"),
    (7, "Social Science", "Exploring Society: India and Beyond Part I", "gees1"), (7, "Social Science", "Exploring Society: India and Beyond Part II", "gees2"),
    (8, "English", "Poorvi", "hepr1"), (8, "Mathematics", "Ganita Prakash Part I", "hegp1"), (8, "Mathematics", "Ganita Prakash Part II", "hegp2"),
    (8, "Hindi", "Malhar", "hhml1"), (8, "Sanskrit", "Deepakam", "hsde1"), (8, "Science", "Curiosity", "hecu1"),
    (8, "Social Science", "Exploring Society: India and Beyond Part I", "hees1"), (8, "Social Science", "Exploring Society: India and Beyond Part II", "hees2"),
    (9, "English", "Kaveri", "iebe1"), (9, "Hindi", "Ganga", "ihga1"), (9, "Sanskrit", "Sharada", "ihsh1"),
    (9, "Mathematics", "Ganita Manjari Part I", "iemh1"), (9, "Mathematics", "Ganita Manjari Part II", "iemh2"),
    (9, "Science", "Exploration", "iesc1"), (9, "Social Science", "Understanding Society: India and Beyond Part I", "iest1"),
    (9, "Social Science", "Understanding Society: India and Beyond Part II", "iest2"),
    (10, "Mathematics", "Mathematics", "jemh1"), (10, "Science", "Science", "jesc1"),
    (10, "English", "First Flight", "jeff1"), (10, "English", "Footprints without Feet", "jefp1"),
    (10, "Hindi Course A", "Kshitij Bhag 2", "jhks1"), (10, "Hindi Course A", "Kritika Bhag 2", "jhkr1"),
    (10, "Hindi Course B", "Sparsh Bhag 2", "jhsp1"), (10, "Hindi Course B", "Sanchayan Bhag 2", "jhsy1"),
    (10, "Social Science", "India and the Contemporary World II", "jess3"), (10, "Social Science", "Contemporary India II", "jess1"),
    (10, "Social Science", "Democratic Politics II", "jess4"), (10, "Social Science", "Understanding Economic Development", "jess2"),
    (10, "Sanskrit", "Shemushi Bhag 2", "jhsk1"),
    (11, "Physics", "Physics Part I", "keph1"), (11, "Physics", "Physics Part II", "keph2"),
    (11, "Chemistry", "Chemistry Part I", "kech1"), (11, "Chemistry", "Chemistry Part II", "kech2"),
    (11, "Mathematics", "Mathematics", "kemh1"), (11, "Biology", "Biology", "kebo1"),
    (11, "English Core", "Hornbill", "kehb1"), (11, "English Core", "Snapshots", "kesp1"),
    (11, "Hindi Core", "Aroh Bhag 1", "khar1"), (11, "Hindi Core", "Vitan Bhag 1", "khvt1"),
    (11, "Accountancy", "Financial Accounting Part I", "keac1"), (11, "Accountancy", "Financial Accounting Part II", "keac2"),
    (11, "Business Studies", "Business Studies", "kebs1"), (11, "Economics", "Statistics for Economics", "kest1"),
    (11, "Economics", "Indian Economic Development", "keec1"),
    (11, "Computer Science", "Computer Science", "kecs1"), (11, "Informatics Practices", "Informatics Practices", "keip1"),
    (11, "History", "Themes in World History", "kehs1"),
    (11, "Geography", "Fundamentals of Physical Geography", "kegy2"), (11, "Geography", "India: Physical Environment", "kegy1"),
    (11, "Political Science", "Political Theory", "keps1"), (11, "Political Science", "Indian Constitution at Work", "keps2"),
    (11, "Psychology", "Introduction to Psychology", "kepy1"),
    (11, "Sociology", "Introducing Sociology", "kesy1"), (11, "Sociology", "Understanding Society", "kesy2"),
    (12, "Physics", "Physics Part I", "leph1"), (12, "Physics", "Physics Part II", "leph2"),
    (12, "Chemistry", "Chemistry Part I", "lech1"), (12, "Chemistry", "Chemistry Part II", "lech2"),
    (12, "Mathematics", "Mathematics Part I", "lemh1"), (12, "Mathematics", "Mathematics Part II", "lemh2"),
    (12, "Biology", "Biology", "lebo1"),
    (12, "English Core", "Flamingo", "lefl1"), (12, "English Core", "Vistas", "levt1"),
    (12, "Hindi Core", "Aroh Bhag 2", "lhar1"), (12, "Hindi Core", "Vitan Bhag 2", "lhvt1"),
    (12, "Accountancy", "Accountancy Part I", "leac1"), (12, "Accountancy", "Accountancy Part II", "leac2"),
    (12, "Business Studies", "Business Studies Part I", "lebs1"), (12, "Business Studies", "Business Studies Part II", "lebs2"),
    (12, "Economics", "Introductory Microeconomics", "leec2"), (12, "Economics", "Introductory Macroeconomics", "leec1"),
    (12, "Computer Science", "Computer Science", "lecs1"), (12, "Informatics Practices", "Informatics Practices", "leip1"),
    (12, "History", "Themes in Indian History Part I", "lehs1"), (12, "History", "Themes in Indian History Part II", "lehs2"),
    (12, "History", "Themes in Indian History Part III", "lehs3"),
    (12, "Geography", "Fundamentals of Human Geography", "legy1"), (12, "Geography", "India: People and Economy", "legy2"),
    (12, "Political Science", "Contemporary World Politics", "leps1"), (12, "Political Science", "Politics in India since Independence", "leps2"),
    (12, "Psychology", "Psychology", "lepy1"),
    (12, "Sociology", "Indian Society", "lesy1"), (12, "Sociology", "Social Change and Development in India", "lesy2"),
]
MARKS = ("contents", "content", "अनुक्रम", "विषय-सूची", "विषय सूची", "अनुक्रमणिका", "विषयानुक्रमणिका", "विषयसूची")

(HERE / "toc").mkdir(parents=True, exist_ok=True)
only = set(sys.argv[1:])
for cls, subject, book, code in BOOKS:
    if only and code not in only:
        continue
    pdf = HERE / f"{code}ps.pdf"
    if not pdf.exists() or pdf.stat().st_size < 2000:
        subprocess.run(["curl", "-sS", "-m", "120", "-A", "Mozilla/5.0", "-o", str(pdf), f"https://ncert.nic.in/textbook/pdf/{code}ps.pdf"], check=False)
    try:
        doc = pymupdf.open(pdf)
    except Exception as exc:  # noqa: BLE001
        print(code, "UNREADABLE", exc)
        continue
    pages = [doc[i].get_text() for i in range(doc.page_count)]
    hits = [i for i, t in enumerate(pages) if any(m in t.lower() for m in MARKS)]
    # the contents is usually the last match; keep it and the page after (contents run over)
    keep = sorted({j for i in hits[-2:] for j in (i, i + 1) if j < len(pages)}) or list(range(max(0, len(pages) - 3), len(pages)))
    text = "\n".join(f"=== page {i}\n{pages[i]}" for i in keep)
    (HERE / "toc" / f"{code}.txt").write_text(f"# {cls} | {subject} | {book} | {code} | pages {doc.page_count}\n{text}", encoding="utf-8")
    print(code, cls, subject, book, "pages", doc.page_count, "contents at", keep)
