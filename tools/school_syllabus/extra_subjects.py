"""Add the CBSE subjects that have no NCERT book to the school syllabus files (run after build_school.py; running it
again changes nothing):

* French, German and Spanish for Classes 6-8: the third language of NEP 2020's three-language formula, which CBSE
  offers alongside Sanskrit. CBSE gives these as themes and grammar by level (a beginner's A1 to A2), not a book.
* Information Technology (402, a skill subject) and Computer Applications (165) for Classes 9-10, as CBSE's
  curriculum documents split them; marks are the theory marks of each unit.

    python -I tools/school_syllabus/extra_subjects.py [backend/app/data/syllabus/school]
"""
import json
import pathlib
import sys

DATA = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[2] / "backend" / "app" / "data" / "syllabus" / "school"

# what each class of a foreign language covers: (theme, its topics)
THEMES = {
    6: [("Greetings and introductions", ["Saying hello and goodbye", "Introducing yourself and others", "Polite expressions", "The alphabet and pronunciation"]),
        ("Numbers, days and months", ["Numbers 0 to 100", "Days of the week", "Months and seasons", "Telling the date"]),
        ("My family", ["Family members", "Describing people", "Possessive adjectives", "Talking about age"]),
        ("My school", ["Classroom objects", "School subjects", "Definite and indefinite articles", "Gender and number of nouns"]),
        ("Colours and clothes", ["Colours", "Clothes", "Adjective agreement", "Likes and dislikes"]),
        ("Food and drinks", ["Common foods and drinks", "Meals of the day", "Ordering politely", "Words of quantity"]),
        ("Regular verbs in the present", ["Subject pronouns", "Regular verbs in the present tense", "Negative sentences", "Asking simple questions"])],
    7: [("My house", ["Rooms and furniture", "Prepositions of place", "Describing your home", "There is and there are"]),
        ("Daily routine", ["Telling the time", "Verbs of the daily routine", "Adverbs of frequency", "A day in my life"]),
        ("Hobbies and sports", ["Free-time activities", "Sports and games", "Saying what you prefer", "Irregular verbs in the present tense"]),
        ("The town and directions", ["Places in a town", "Asking and giving directions", "Means of transport", "The imperative"]),
        ("Weather and seasons", ["Weather expressions", "Seasons and festivals", "Describing the climate"]),
        ("Shopping", ["Shops and products", "Prices and money", "Buying and selling", "Demonstrative adjectives"]),
        ("Reading and writing I", ["Short passages", "Writing a message", "Filling in a form", "Describing a picture"])],
    8: [("Body and health", ["Parts of the body", "At the doctor's", "Healthy habits", "Saying how you feel"]),
        ("Travel and holidays", ["Countries and nationalities", "Planning a trip", "The near future", "Holiday postcards"]),
        ("Talking about the past", ["The past tense", "Time expressions for the past", "What I did last weekend"]),
        ("Festivals and culture", ["Festivals of the countries that speak the language", "Indian festivals described in the language", "Food and customs"]),
        ("Environment and nature", ["Animals and plants", "Protecting the environment", "Comparatives and superlatives"]),
        ("Technology and media", ["Computers and phones", "Using the internet safely", "Giving your opinion"]),
        ("Reading and writing II", ["Comprehension passages", "Informal letters and emails", "Writing a short paragraph", "Completing a dialogue"])],
}
LEVEL = {6: "Level 1 (A1, part 1)", 7: "Level 2 (A1, part 2)", 8: "Level 3 (A2)"}
OWN_NAME = {"French": "Français", "German": "Deutsch", "Spanish": "Español"}


def language(lang: str, cls: int) -> dict:
    # chapter names carry the class: a chapter's name is unique within its subject across the classes
    return {"name": lang, "units": [{"name": f"{OWN_NAME[lang]}: {LEVEL[cls]}", "chapters": [
        {"name": f"{theme} (Class {cls})", "topics": topics} for theme, topics in THEMES[cls]]}]}


def ch(name: str, marks: float, topics: list[str]) -> dict:
    return {"name": name, "marks": marks, "topics": topics}


IT = {
    9: [{"name": "Part A: Employability Skills", "chapters": [
            ch("Communication Skills I", 2, ["Methods and process of communication", "Verbal and non-verbal communication", "Barriers to communication", "Pronunciation and parts of speech", "Greetings and introductions"]),
            ch("Self-Management Skills I", 2, ["Stress management", "Self-awareness: strengths and weaknesses", "Self-motivation", "Self-regulation and goal setting"]),
            ch("ICT Skills I", 2, ["Role of ICT in daily life", "Smartphones and tablets", "Computer peripherals", "Basic computer operations", "Communication technologies"]),
            ch("Entrepreneurial Skills I", 2, ["Entrepreneurship and society", "Qualities and functions of an entrepreneur", "Myths about entrepreneurship", "Entrepreneurship as a career"]),
            ch("Green Skills I", 2, ["Society and environment", "Conserving natural resources", "Sustainable development", "Green economy"])]},
        {"name": "Part B: Subject Skills", "chapters": [
            ch("Introduction to IT-ITeS Industry", 5, ["IT and ITeS", "IT at home, at work and in society", "BPO, KPO and the IT industry in India"]),
            ch("Data Entry and Keyboarding Skills", 5, ["Keyboard layout and the home row", "Touch typing", "Typing speed and accuracy", "Ergonomics"]),
            ch("Digital Documentation", 10, ["Creating, saving and printing a document", "Formatting text and paragraphs", "Lists, tables and images", "Page layout, headers and footers", "Spelling and grammar check"]),
            ch("Electronic Spreadsheet", 10, ["Rows, columns and cells", "Entering data and formulas", "Cell references", "SUM, AVERAGE, MAX and MIN", "Formatting and charts"]),
            ch("Digital Presentation", 10, ["Creating a presentation", "Slide layouts and themes", "Images, tables and charts", "Transitions and animations", "Running and printing a slide show"])]}],
    10: [{"name": "Part A: Employability Skills", "chapters": [
            ch("Communication Skills II", 2, ["The communication cycle", "The 7 Cs of effective communication", "Writing sentences and paragraphs", "Feedback"]),
            ch("Self-Management Skills II", 2, ["Self-motivation", "Time management", "Working independently", "Personal grooming"]),
            ch("ICT Skills II", 2, ["Operating systems and files", "Care and maintenance of a computer", "Computer security and privacy", "Viruses and backups"]),
            ch("Entrepreneurial Skills II", 2, ["Entrepreneurship and society", "Barriers to entrepreneurship", "Entrepreneurial attitudes", "Business ideas and planning"]),
            ch("Green Skills II", 2, ["Sustainable development goals", "Green jobs", "Why green jobs matter"])]},
         {"name": "Part B: Subject Skills", "chapters": [
            ch("Digital Documentation (Advanced)", 10, ["Styles", "Inserting and using images", "Templates", "Table of contents", "Mail merge"]),
            ch("Electronic Spreadsheet (Advanced)", 10, ["Consolidating data", "Subtotals and data tables", "Scenarios and goal seek", "Linking sheets and files", "Sharing and tracking changes", "Macros"]),
            ch("Database Management System", 10, ["Data and databases", "Tables, fields and records", "Primary and foreign keys", "Tables and relationships", "Queries and SQL basics", "Forms and reports"]),
            ch("Web Applications and Security", 10, ["Networking fundamentals", "Instant messaging and blogging", "Online transactions and shopping", "Internet security and safe passwords", "Occupational health and safety"])]}],
}
CA = {
    9: [ch("Basics of Information Technology", 10, ["The computer system and its parts", "Input and output devices", "Memory and storage units", "Types of software", "Operating systems"]),
        ch("Cyber Safety", 10, ["Safe browsing", "Protecting your identity", "Keeping information confidential", "Cyber trolls and bullying", "Malware and safe email"]),
        ch("Office Tools", 10, ["Word processor", "Presentation tool", "Spreadsheet tool"]),
        ch("Lab Exercises: Scratch or Python", 20, ["Algorithms and flowcharts", "Variables and data types", "Conditions and loops", "Simple programs"])],
    10: [ch("Networking", 15, ["The internet and the World Wide Web", "LAN, MAN, WAN and PAN", "Network devices", "Email, chat, video conferencing and e-learning", "HTTP, FTP and TCP/IP", "Web servers and hosting"]),
         ch("HTML", 25, ["Structure of an HTML page", "Text formatting", "Lists", "Images and links", "Tables", "Forms", "Audio and video", "CSS basics"]),
         ch("Cyber Ethics", 10, ["Netiquette", "Software licences and open source", "Intellectual property and plagiarism", "Digital property rights", "Freedom of information and the digital divide", "E-commerce and its security"])],
}


def write(cls: int, add: list[dict], default: list[str]) -> None:
    path = DATA / f"class_{cls:02d}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    have = {s["name"] for s in data["subjects"]}
    data["subjects"] += [s for s in add if s["name"] not in have]
    data["default"] = default
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


for n in (6, 7, 8):
    write(n, [language(lang, n) for lang in OWN_NAME], ["English", "Hindi", "Mathematics", "Science", "Social Science", "Sanskrit"])
write(9, [{"name": "Information Technology", "units": IT[9]}, {"name": "Computer Applications", "units": [{"name": "Computer Applications (165)", "chapters": CA[9]}]}],
      ["English", "Hindi", "Mathematics", "Science", "Social Science", "Information Technology"])
write(10, [{"name": "Information Technology", "units": IT[10]}, {"name": "Computer Applications", "units": [{"name": "Computer Applications (165)", "chapters": CA[10]}]}],
      ["English", "Hindi Course A", "Mathematics", "Science", "Social Science", "Information Technology"])
print("added the languages (6-8) and IT / Computer Applications (9-10)")
