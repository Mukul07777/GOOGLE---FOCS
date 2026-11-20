"""Classes 11 and 12, by NCERT book, in the CBSE curriculum 2026-27 (marks per unit spread over its chapters;
chapters CBSE has dropped for the year start with "-"). Class 11's science subjects are kept from class_11.json."""

C11 = {"default": ["Physics", "Chemistry", "Mathematics", "Biology", "English Core"], "keep": ["Physics", "Chemistry", "Mathematics", "Biology"], "subjects": [
    ("English Core", [
        ("Hornbill", "Hornbill", "kehb1", 1, None, ["The Portrait of a Lady", "A Photograph", "We're Not Afraid to Die... if We Can All Be Together",
                                                 "Discovering Tut: the Saga Continues", "The Laburnum Top", "The Voice of the Rain",
                                                 "The Ailing Planet: the Green Movement's Role", "Childhood", "The Adventure", "Silk Road", "Father to Son"]),
        ("Snapshots", "Snapshots", "kesp1", 1, None, ["The Summer of the Beautiful White Horse", "The Address", "Mother's Day", "Birth", "The Tale of Melon City"]),
    ]),
    ("Hindi Core", [
        ("आरोह भाग 1: गद्य खंड", "आरोह भाग 1", "khar1", 1, None, ["नमक का दारोगा", "मियाँ नसीरुद्दीन", "अपू के साथ ढाई साल", "विदाई-संभाषण", "गलता लोहा", "रजनी",
                                                                "जामुन का पेड़", "भारत माता"]),
        ("आरोह भाग 1: काव्य खंड", "आरोह भाग 1", "khar1", 9, None, ["हम तौ एक एक करि जांनां (कबीर)", "मेरे तो गिरधर गोपाल, दूसरो न कोई (मीरा)", "घर की याद",
                                                                 "चंपा काले-काले अच्छर नहीं चीन्हती", "ग़ज़ल (दुष्यंत कुमार)", "हे भूख! मत मचल (अक्कमहादेवी)",
                                                                 "सबसे ख़तरनाक", "आओ, मिलकर बचाएँ"]),
        ("वितान भाग 1", "वितान भाग 1", "khvt1", 1, None, ["भारतीय गायिकाओं में बेजोड़: लता मंगेशकर", "राजस्थान की रजत बूँदें", "आलो-आँधारि"]),
    ]),
    ("Accountancy", [
        ("Theoretical Framework", "Financial Accounting Part I", "keac1", 1, 12, ["Introduction to Accounting", "Theory Base of Accounting"]),
        ("Accounting Process", "Financial Accounting Part I", "keac1", 3, 44, ["Recording of Transactions – I", "Recording of Transactions – II", "Bank Reconciliation Statement",
                                                                              "Trial Balance and Rectification of Errors", "Depreciation, Provisions and Reserves"]),
        ("Financial Statements of Sole Proprietorship", "Financial Accounting Part II", "keac2", 1, 24, ["Financial Statements – I", "Financial Statements – II"]),
    ]),
    ("Business Studies", [
        ("Foundations of Business", "Business Studies", "kebs1", 1, None, [
            {"name": "Business, Trade and Commerce", "marks": 8}, {"name": "Forms of Business Organisation", "marks": 8},
            {"name": "Private, Public and Global Enterprises", "marks": 7}, {"name": "Business Services", "marks": 7},
            {"name": "Emerging Modes of Business", "marks": 5}, {"name": "Social Responsibilities of Business and Business Ethics", "marks": 5}]),
        ("Finance and Trade", "Business Studies", "kebs1", 7, None, [
            "-Formation of a Company", {"name": "Sources of Business Finance", "marks": 10}, {"name": "MSME and Business Entrepreneurship", "marks": 10},
            {"name": "Internal Trade", "marks": 10}, {"name": "International Business", "marks": 10}]),
    ]),
    ("Economics", [
        ("Statistics for Economics", "Statistics for Economics", "kest1", 1, None, [
            {"name": "Introduction", "marks": 3.75}, {"name": "Collection of Data", "marks": 3.75}, {"name": "Organisation of Data", "marks": 3.75},
            {"name": "Presentation of Data", "marks": 3.75}, {"name": "Measures of Central Tendency", "marks": 8.33}, {"name": "Correlation", "marks": 8.33},
            {"name": "Index Numbers", "marks": 8.33}, "-Use of Statistical Tools"]),
        ("Introductory Microeconomics", "Introductory Microeconomics", "leec2", 1, None, [
            {"name": "Introduction to Microeconomics", "marks": 4}, {"name": "Theory of Consumer Behaviour", "marks": 14}, {"name": "Production and Costs", "marks": 7},
            {"name": "The Theory of the Firm under Perfect Competition", "marks": 7}, {"name": "Market Equilibrium", "marks": 8}]),
    ]),
    ("Computer Science", [
        ("Computer Systems and Organisation", "Computer Science", "kecs1", 1, 10, ["Computer System", "Encoding Schemes and Number System"]),
        ("Emerging Trends", "Computer Science", "kecs1", 3, None, ["-Emerging Trends"]),
        ("Computational Thinking and Programming", "Computer Science", "kecs1", 4, 45, ["Introduction to Problem Solving", "Getting Started with Python", "Flow of Control",
                                                                                       "Functions", "Strings", "Lists", "Tuples and Dictionaries"]),
        ("Society, Law and Ethics", "Computer Science", "kecs1", 11, 15, ["Societal Impact"]),
    ]),
    ("Informatics Practices", [
        ("Introduction to Computer System", "Informatics Practices", "keip1", 1, 10, ["Computer System"]),
        ("Introduction to Emerging Trends", "Informatics Practices", "keip1", 2, 5, ["Emerging Trends"]),
        ("Introduction to Python", "Informatics Practices", "keip1", 3, 25, ["Brief Overview of Python", "Working with Lists and Dictionaries"]),
        ("Data and NumPy", "Informatics Practices", "keip1", 5, None, ["-Understanding Data", "-Introduction to NumPy"]),
        ("Database Concepts and SQL", "Informatics Practices", "keip1", 7, 30, ["Database Concepts", "Introduction to Structured Query Language (SQL)"]),
    ]),
    ("History", [
        ("Early Societies", "Themes in World History", "kehs1", 1, 10, ["Writing and City Life"]),
        ("Empires", "Themes in World History", "kehs1", 2, 20, ["An Empire Across Three Continents", "Nomadic Empires"]),
        ("Changing Traditions", "Themes in World History", "kehs1", 4, 20, ["The Three Orders", "Changing Cultural Traditions"]),
        ("Towards Modernisation", "Themes in World History", "kehs1", 6, None, [{"name": "Displacing Indigenous Peoples", "marks": 10}, {"name": "Paths to Modernisation", "marks": 15}]),
    ]),
    ("Geography", [
        ("Fundamentals of Physical Geography", "Fundamentals of Physical Geography", "kegy2", 1, None, [
            {"name": "Geography as a Discipline", "marks": 3}, {"name": "The Origin and Evolution of the Earth", "marks": 3}, {"name": "Interior of the Earth", "marks": 3},
            {"name": "Distribution of Oceans and Continents", "marks": 3}, {"name": "Geomorphic Processes", "marks": 3}, {"name": "Landforms and their Evolution", "marks": 3},
            {"name": "Composition and Structure of Atmosphere", "marks": 2}, {"name": "Solar Radiation, Heat Balance and Temperature", "marks": 2},
            {"name": "Atmospheric Circulation and Weather Systems", "marks": 2}, {"name": "Water in the Atmosphere", "marks": 2},
            "-World Climate and Climate Change", {"name": "Water (Oceans)", "marks": 2}, {"name": "Movements of Ocean Water", "marks": 2},
            {"name": "Biodiversity and Conservation", "marks": 2}]),
        ("India: Physical Environment", "India: Physical Environment", "kegy1", 1, None, ["India — Location", "Structure and Physiography", "Drainage System", "Climate",
                                                                                       "Natural Vegetation", "Natural Hazards and Disasters"]),
    ]),
    ("Political Science", [
        ("Indian Constitution at Work", "Indian Constitution at Work", "keps2", 1, None, [
            {"name": "Constitution: Why and How?", "marks": 4}, {"name": "Rights in the Indian Constitution", "marks": 4}, {"name": "Election and Representation", "marks": 6},
            {"name": "Executive", "marks": 4}, {"name": "Legislature", "marks": 4}, {"name": "Judiciary", "marks": 4}, {"name": "Federalism", "marks": 6},
            {"name": "Local Governments", "marks": 4}, {"name": "Constitution as a Living Document", "marks": 2}, {"name": "The Philosophy of the Constitution", "marks": 2}]),
        ("Political Theory", "Political Theory", "keps1", 1, None, [
            {"name": "Political Theory: An Introduction", "marks": 4}, {"name": "Freedom", "marks": 6}, {"name": "Equality", "marks": 6}, {"name": "Social Justice", "marks": 6},
            {"name": "Rights", "marks": 4}, {"name": "Citizenship", "marks": 4}, {"name": "Nationalism", "marks": 4}, {"name": "Secularism", "marks": 6}]),
    ]),
    ("Psychology", [
        ("Introduction to Psychology", "Introduction to Psychology", "kepy1", 1, None, [
            {"name": "What is Psychology?", "marks": 11}, {"name": "Methods of Enquiry in Psychology", "marks": 13}, {"name": "Human Development", "marks": 11},
            {"name": "Sensory, Attentional and Perceptual Processes", "marks": 8}, {"name": "Learning", "marks": 9}, {"name": "Human Memory", "marks": 8},
            {"name": "Thinking", "marks": 5}, {"name": "Motivation and Emotion", "marks": 5}]),
    ]),
    ("Sociology", [
        ("Introducing Sociology", "Introducing Sociology", "kesy1", 1, None, [
            {"name": "Sociology and Society", "marks": 10}, {"name": "Terms, Concepts and their Use in Sociology", "marks": 10},
            {"name": "Understanding Social Institutions", "marks": 12}, {"name": "Culture and Socialisation", "marks": 12}, "-Doing Sociology: Research Methods"]),
        ("Understanding Society", "Understanding Society", "kesy2", 1, None, [
            "-Social Structure, Stratification and Social Processes in Society", {"name": "Social Change and Social Order in Rural and Urban Society", "marks": 12},
            "-Environment and Society", {"name": "Introducing Western Sociologists", "marks": 12}, {"name": "Indian Sociologists", "marks": 12}]),
    ]),
]}


def T(name, topics, marks=None):
    return {"name": name, "topics": topics, **({"marks": marks} if marks is not None else {})}


C12 = {"default": ["Physics", "Chemistry", "Mathematics", "Biology", "English Core"], "subjects": [
    ("Physics", [
        ("Electrostatics and Current Electricity", "Physics Part I", "leph1", 1, 16, [
            T("Electric Charges and Fields", ["Electric charge and its conservation", "Coulomb's law", "Forces between multiple charges; superposition", "Continuous charge distributions",
                                              "Electric field and field lines", "Electric dipole; torque in a uniform field", "Electric flux and Gauss's law",
                                              "Field of a long wire, a plane sheet and a thin spherical shell"]),
            T("Electrostatic Potential and Capacitance", ["Electric potential and potential difference", "Potential of a point charge, a dipole and a system of charges",
                                                         "Equipotential surfaces", "Potential energy of a system of charges and of a dipole",
                                                         "Conductors, dielectrics and polarisation", "Capacitors in series and in parallel",
                                                         "Parallel plate capacitor with and without a dielectric", "Energy stored in a capacitor"]),
            T("Current Electricity", ["Electric current and drift velocity", "Ohm's law and V-I characteristics", "Resistivity and its temperature dependence",
                                      "Electrical energy and power", "EMF, internal resistance and combinations of cells", "Kirchhoff's rules", "Wheatstone bridge"]),
        ]),
        ("Magnetism, Induction and Alternating Current", "Physics Part I", "leph1", 4, 17, [
            T("Moving Charges and Magnetism", ["Magnetic field and Oersted's experiment", "Biot-Savart law: field of a circular loop", "Ampere's law: long straight wire and solenoid",
                                               "Force on a moving charge in magnetic and electric fields", "Force on a current-carrying conductor; parallel currents",
                                               "Torque on a current loop; magnetic dipole moment", "Moving coil galvanometer, ammeter and voltmeter"]),
            T("Magnetism and Matter", ["Bar magnet as an equivalent solenoid", "Field of a magnetic dipole", "Torque on a magnetic dipole in a uniform field",
                                       "Magnetic field lines", "Para-, dia- and ferromagnetic substances", "Magnetisation and the effect of temperature"]),
            T("Electromagnetic Induction", ["Faraday's laws of induction", "Induced EMF and current", "Lenz's law", "Self-induction", "Mutual induction"]),
            T("Alternating Current", ["Peak and RMS values", "Reactance and impedance", "LCR series circuit with phasors", "Resonance",
                                      "Power in AC circuits, power factor and wattless current", "AC generator and transformer"]),
        ]),
        ("Electromagnetic Waves and Optics", "Physics Part I and II", "leph1", 8, 18, [
            T("Electromagnetic Waves", ["Displacement current", "Electromagnetic waves and their transverse nature", "The electromagnetic spectrum and its uses"]),
            T("Ray Optics and Optical Instruments", ["Reflection and spherical mirrors", "Refraction and total internal reflection; optical fibres",
                                                     "Refraction at spherical surfaces and lenses", "Lens maker's formula, magnification and power",
                                                     "Combination of thin lenses", "Refraction through a prism", "Microscopes and telescopes"]),
            T("Wave Optics", ["Wavefronts and Huygens' principle", "Reflection and refraction using wavefronts", "Interference and Young's double-slit experiment",
                              "Coherent sources", "Diffraction at a single slit"]),
        ]),
        ("Dual Nature, Atoms and Nuclei", "Physics Part II", "leph2", 3, 12, [
            T("Dual Nature of Radiation and Matter", ["Dual nature of radiation", "Photoelectric effect: Hertz's and Lenard's observations", "Einstein's photoelectric equation",
                                                      "Experimental study of the photoelectric effect", "Matter waves and the de Broglie relation"]),
            T("Atoms", ["Alpha-particle scattering experiment", "Rutherford's model of the atom", "Bohr model: radius, velocity and energy of the nth orbit", "Hydrogen line spectra"]),
            T("Nuclei", ["Composition and size of the nucleus", "Nuclear force", "Mass-energy relation and mass defect", "Binding energy per nucleon", "Nuclear fission and fusion"]),
        ]),
        ("Electronic Devices", "Physics Part II", "leph2", 6, 7, [
            T("Semiconductor Electronics: Materials, Devices and Simple Circuits", ["Energy bands in conductors, semiconductors and insulators",
                                                                                 "Intrinsic and extrinsic semiconductors", "The p-n junction",
                                                                                 "Diode in forward and reverse bias", "Diode as a rectifier"]),
        ]),
    ]),
    ("Chemistry", [
        ("Chemistry Part I", "Chemistry Part I", "lech1", 1, None, [
            T("Solutions", ["Types of solutions", "Expressing concentration", "Solubility", "Vapour pressure of liquid solutions", "Ideal and non-ideal solutions",
                            "Colligative properties and molar mass", "Abnormal molar masses"], 7),
            T("Electrochemistry", ["Electrochemical and galvanic cells", "Nernst equation", "Conductance of electrolytic solutions", "Electrolytic cells and electrolysis",
                                   "Batteries and fuel cells", "Corrosion"], 9),
            T("Chemical Kinetics", ["Rate of a chemical reaction", "Factors influencing the rate", "Integrated rate equations", "Temperature dependence of the rate",
                                    "Collision theory"], 7),
            T("The d- and f-Block Elements", ["Position in the periodic table", "Electronic configuration of d-block elements", "General properties of transition elements",
                                              "Important compounds of transition elements", "The lanthanoids", "The actinoids", "Applications of d- and f-block elements"], 7),
            T("Coordination Compounds", ["Werner's theory", "Important terms", "Nomenclature", "Isomerism in coordination compounds", "Bonding in coordination compounds",
                                         "Bonding in metal carbonyls", "Importance and applications"], 7),
        ]),
        ("Chemistry Part II", "Chemistry Part II", "lech2", 1, None, [
            T("Haloalkanes and Haloarenes", ["Classification and nomenclature", "Nature of the C-X bond", "Preparation of haloalkanes and haloarenes", "Physical properties",
                                             "Chemical reactions", "Polyhalogen compounds"], 6),
            T("Alcohols, Phenols and Ethers", ["Classification and nomenclature", "Structures of the functional groups", "Alcohols and phenols: preparation and reactions",
                                               "Commercially important alcohols", "Ethers"], 6),
            T("Aldehydes, Ketones and Carboxylic Acids", ["The carbonyl group", "Preparation of aldehydes and ketones", "Properties and reactions of aldehydes and ketones",
                                                          "Uses of aldehydes and ketones", "The carboxyl group and preparation of carboxylic acids",
                                                          "Properties, reactions and uses of carboxylic acids"], 8),
            T("Amines", ["Structure, classification and nomenclature", "Preparation of amines", "Properties and reactions of amines", "Diazonium salts: preparation and properties",
                         "Diazonium salts in the synthesis of aromatic compounds"], 6),
            T("Biomolecules", ["Carbohydrates", "Proteins", "Enzymes", "Vitamins", "Nucleic acids", "Hormones"], 7),
        ]),
    ]),
    ("Mathematics", [
        ("Relations and Functions", "Mathematics Part I", "lemh1", 1, 8, [
            T("Relations and Functions", ["Reflexive, symmetric and transitive relations", "Equivalence relations", "One-one and onto functions"]),
            T("Inverse Trigonometric Functions", ["Definition, domain and range", "Principal value branches", "Graphs of inverse trigonometric functions"]),
        ]),
        ("Algebra", "Mathematics Part I", "lemh1", 3, 10, [
            T("Matrices", ["Order, equality and types of matrices", "Transpose; symmetric and skew-symmetric matrices", "Addition and scalar multiplication",
                           "Multiplication of matrices", "Invertible matrices and uniqueness of the inverse"]),
            T("Determinants", ["Determinants up to 3 x 3", "Minors and cofactors", "Area of a triangle", "Adjoint and inverse of a matrix",
                               "Consistency of a system of linear equations", "Solving linear equations with the inverse of a matrix"]),
        ]),
        ("Calculus", "Mathematics Part I and II", "lemh1", 5, 35, [
            T("Continuity and Differentiability", ["Continuity and differentiability", "Chain rule", "Derivatives of inverse trigonometric functions", "Implicit functions",
                                                  "Exponential and logarithmic functions", "Logarithmic differentiation", "Parametric forms", "Second-order derivatives"]),
            T("Application of Derivatives", ["Rate of change of quantities", "Increasing and decreasing functions", "Maxima and minima: first derivative test",
                                             "Second derivative test", "Real-life optimisation problems"]),
            T("Integrals", ["Integration as the inverse of differentiation", "Integration by substitution", "Integration by partial fractions", "Integration by parts",
                            "Integrals of special forms", "Fundamental theorem of calculus", "Properties of definite integrals"]),
            T("Application of Integrals", ["Area under simple curves", "Area bounded by lines, circles, parabolas and ellipses"]),
            T("Differential Equations", ["Order and degree", "General and particular solutions", "Variables separable", "Homogeneous differential equations",
                                         "Linear differential equations"]),
        ]),
        ("Vectors and Three-Dimensional Geometry", "Mathematics Part II", "lemh2", 4, 14, [
            T("Vector Algebra", ["Vectors and scalars; magnitude and direction", "Direction cosines and ratios", "Types of vectors", "Addition and scalar multiplication",
                                 "Section formula", "Scalar (dot) product", "Vector (cross) product"]),
            T("Three Dimensional Geometry", ["Direction cosines and ratios of a line", "Vector and Cartesian equations of a line", "Angle between two lines",
                                             "Skew lines and the shortest distance"]),
        ]),
        ("Linear Programming", "Mathematics Part II", "lemh2", 6, 5, [
            T("Linear Programming", ["Constraints and the objective function", "Graphical method in two variables", "Feasible and infeasible regions", "Optimal solutions"]),
        ]),
        ("Probability", "Mathematics Part II", "lemh2", 7, 8, [
            T("Probability", ["Conditional probability", "Multiplication theorem", "Independent events", "Theorem of total probability", "Bayes' theorem"]),
        ]),
    ]),
    ("Biology", [
        ("Reproduction", "Biology", "lebo1", 1, 16, [
            T("Sexual Reproduction in Flowering Plants", ["Flower structure", "Male and female gametophytes", "Pollination: types and agencies", "Outbreeding devices",
                                                         "Pollen-pistil interaction and double fertilisation", "Endosperm, embryo, seed and fruit",
                                                         "Apomixis, parthenocarpy and polyembryony"]),
            T("Human Reproduction", ["Male and female reproductive systems", "Gametogenesis", "Menstrual cycle", "Fertilisation and implantation",
                                     "Pregnancy and placenta", "Parturition and lactation"]),
            T("Reproductive Health", ["Reproductive health and STDs", "Birth control methods", "Medical termination of pregnancy", "Amniocentesis",
                                      "Infertility and assisted reproductive technologies"]),
        ]),
        ("Genetics and Evolution", "Biology", "lebo1", 4, 20, [
            T("Principles of Inheritance and Variation", ["Mendelian inheritance", "Incomplete dominance, co-dominance and multiple alleles", "Chromosomal theory of inheritance",
                                                          "Sex determination", "Linkage and crossing over", "Sex-linked inheritance", "Mendelian and chromosomal disorders"]),
            T("Molecular Basis of Inheritance", ["DNA as the genetic material", "Structure of DNA and RNA; packaging", "DNA replication", "Transcription",
                                                 "Genetic code and translation", "Regulation of gene expression: lac operon", "Human Genome Project and DNA fingerprinting"]),
            T("Evolution", ["Origin of life", "Evidences for evolution", "Darwin and the modern synthetic theory", "Mechanism of evolution and natural selection",
                            "Gene flow, genetic drift and Hardy-Weinberg principle", "Adaptive radiation", "Human evolution"]),
        ]),
        ("Biology and Human Welfare", "Biology", "lebo1", 7, 12, [
            T("Human Health and Disease", ["Pathogens and common human diseases", "Immunity and vaccines", "Cancer", "HIV and AIDS", "Drug and alcohol abuse in adolescence"]),
            T("Microbes in Human Welfare", ["Microbes in household products", "Industrial production", "Sewage treatment", "Biogas", "Bio-control agents and biofertilisers"]),
        ]),
        ("Biotechnology and its Applications", "Biology", "lebo1", 9, 12, [
            T("Biotechnology: Principles and Processes", ["Principles of biotechnology", "Tools of recombinant DNA technology", "Processes of recombinant DNA technology"]),
            T("Biotechnology and its Applications", ["Applications in agriculture: Bt crops", "Applications in medicine: insulin and gene therapy", "Transgenic animals",
                                                     "Ethical issues, biopiracy and patents"]),
        ]),
        ("Ecology and Environment", "Biology", "lebo1", 11, 10, [
            T("Organisms and Populations", ["Population attributes", "Population growth", "Population interactions: mutualism, competition, predation, parasitism"]),
            T("Ecosystem", ["Structure and function", "Productivity", "Decomposition", "Energy flow", "Ecological pyramids"]),
            T("Biodiversity and Conservation", ["Biodiversity: concept and patterns", "Importance of biodiversity", "Loss of biodiversity", "Conservation: in situ and ex situ",
                                                "Hotspots, sacred groves, biosphere reserves and national parks"]),
        ]),
    ]),
    ("English Core", [
        ("Flamingo: Prose", "Flamingo", "lefl1", 1, None, ["The Last Lesson", "Lost Spring", "Deep Water", "The Rattrap", "Indigo", "Poets and Pancakes", "The Interview",
                                                        "Going Places"]),
        ("Flamingo: Poetry", "Flamingo", "lefl1", 9, None, ["My Mother at Sixty-six", "Keeping Quiet", "A Thing of Beauty", "A Roadside Stand", "Aunt Jennifer's Tigers"]),
        ("Vistas", "Vistas", "levt1", 1, None, ["The Third Level", "The Tiger King", "Journey to the End of the Earth", "The Enemy", "On the Face of It", "Memories of Childhood"]),
    ]),
    ("Hindi Core", [
        ("आरोह भाग 2: काव्य खंड", "आरोह भाग 2", "lhar1", 1, None, ["आत्मपरिचय, एक गीत", "पतंग", "कविता के बहाने, बात सीधी थी पर", "कैमरे में बंद अपाहिज", "उषा", "बादल राग",
                                                                 "कवितावली, लक्ष्मण-मूर्च्छा और राम का विलाप", "रुबाइयाँ", "छोटा मेरा खेत, बगुलों के पंख"]),
        ("आरोह भाग 2: गद्य खंड", "आरोह भाग 2", "lhar1", 10, None, ["भक्तिन", "बाज़ार दर्शन", "काले मेघा पानी दे", "पहलवान की ढोलक", "शिरीष के फूल",
                                                                  "श्रम-विभाजन और जाति-प्रथा, मेरी कल्पना का आदर्श समाज"]),
        ("वितान भाग 2", "वितान भाग 2", "lhvt1", 1, None, ["सिल्वर वैडिंग", "जूझ", "अतीत में दबे पाँव"]),
    ]),
    ("Accountancy", [
        ("Accounting for Partnership Firms", "Accountancy Part I", "leac1", 1, 36, ["Accounting for Partnership: Basic Concepts", "Reconstitution of a Partnership Firm – Admission of a Partner",
                                                                                   "Reconstitution of a Partnership Firm – Retirement/Death of a Partner", "Dissolution of Partnership Firm"]),
        ("Accounting for Companies", "Accountancy Part II", "leac2", 1, 24, ["Accounting for Share Capital", "Issue and Redemption of Debentures"]),
        ("Analysis of Financial Statements", "Accountancy Part II", "leac2", 3, None, [{"name": "Financial Statements of a Company", "marks": 4}, {"name": "Analysis of Financial Statements", "marks": 4},
                                                                                     {"name": "Accounting Ratios", "marks": 4}, {"name": "Cash Flow Statement", "marks": 8}]),
    ]),
    ("Business Studies", [
        ("Principles and Functions of Management", "Business Studies Part I", "lebs1", 1, None, [
            {"name": "Nature and Significance of Management", "marks": 8}, {"name": "Principles of Management", "marks": 8}, {"name": "Business Environment", "marks": 7},
            {"name": "Planning", "marks": 7}, {"name": "Organising", "marks": 5}, {"name": "Staffing", "marks": 5}, {"name": "Directing", "marks": 5}, {"name": "Controlling", "marks": 5}]),
        ("Business Finance and Marketing", "Business Studies Part II", "lebs2", 1, None, [
            {"name": "Financial Management", "marks": 7.5},
            {"name": "Financial Markets", "marks": 7.5, "nopdf": True, "book": "CBSE curriculum (not in the NCERT book)", "topics": [
                "Financial markets: concept and functions", "Money market and its instruments", "Capital market: primary and secondary",
                "Stock exchange: functions and trading", "SEBI: objectives and functions"]},
            {"name": "Marketing", "marks": 7.5}, {"name": "Consumer Protection", "marks": 7.5}]),
    ]),
    ("Economics", [
        ("Introductory Macroeconomics", "Introductory Macroeconomics", "leec1", 1, None, [
            {"name": "Introduction to Macroeconomics", "marks": 2}, {"name": "National Income Accounting", "marks": 8}, {"name": "Money and Banking", "marks": 6},
            {"name": "Determination of Income and Employment", "marks": 12}, {"name": "Government Budget and the Economy", "marks": 6},
            {"name": "Open Economy Macroeconomics", "marks": 6}]),
        ("Indian Economic Development", "Indian Economic Development", "keec1", 1, None, [
            {"name": "Indian Economy on the Eve of Independence", "marks": 4}, {"name": "Indian Economy 1950–1990", "marks": 4},
            {"name": "Liberalisation, Privatisation and Globalisation: An Appraisal", "marks": 4}, {"name": "Human Capital Formation in India", "marks": 5},
            {"name": "Rural Development", "marks": 5}, {"name": "Employment: Growth, Informalisation and Other Issues", "marks": 5},
            {"name": "Environment and Sustainable Development", "marks": 5}, {"name": "Comparative Development Experiences of India and its Neighbours", "marks": 8}]),
    ]),
    ("Computer Science", [
        ("Computational Thinking and Programming", "Computer Science", "lecs1", 1, 40, ["Exception Handling in Python", "File Handling in Python", "Stack"]),
        ("Data Structures and Data", "Computer Science", "lecs1", 4, None, ["-Queue", "-Sorting", "-Searching", "-Understanding Data"]),
        ("Database Management", "Computer Science", "lecs1", 8, 20, ["Database Concepts", "Structured Query Language (SQL)"]),
        ("Computer Networks", "Computer Science", "lecs1", 10, 10, ["Computer Networks", "Data Communication"]),
        ("Security", "Computer Science", "lecs1", 12, None, ["Security Aspects", "-Project Based Learning"]),
    ]),
    ("Informatics Practices", [
        ("Database Query using SQL", "Informatics Practices", "leip1", 1, 25, ["Querying and SQL Functions"]),
        ("Data Handling using Pandas and Data Visualisation", "Informatics Practices", "leip1", 2, 25, ["Data Handling using Pandas – I", "Data Handling using Pandas – II",
                                                                                                         "Plotting Data using Matplotlib"]),
        ("Introduction to Computer Networks", "Informatics Practices", "leip1", 5, 10, ["Internet and Web"]),
        ("Societal Impacts", "Informatics Practices", "leip1", 6, 10, ["Societal Impacts", "-Project Based Learning"]),
    ]),
    ("History", [
        ("Themes in Indian History Part I", "Themes in Indian History Part I", "lehs1", 1, 25, ["Bricks, Beads and Bones: The Harappan Civilisation", "Kings, Farmers and Towns",
                                                                                             "Kinship, Caste and Class", "Thinkers, Beliefs and Buildings"]),
        ("Themes in Indian History Part II", "Themes in Indian History Part II", "lehs2", 1, 25, ["Through the Eyes of Travellers", "Bhakti-Sufi Traditions",
                                                                                               "An Imperial Capital: Vijayanagara", "Peasants, Zamindars and the State"]),
        ("Themes in Indian History Part III", "Themes in Indian History Part III", "lehs3", 1, 25, ["Colonialism and the Countryside", "Rebels and the Raj",
                                                                                                 "Mahatma Gandhi and the Nationalist Movement", "Framing the Constitution"]),
    ]),
    ("Geography", [
        ("Fundamentals of Human Geography", "Fundamentals of Human Geography", "legy1", 1, None, ["Human Geography: Nature and Scope", "The World Population: Distribution, Density and Growth",
                                                                                               "Human Development", "Primary Activities", "Secondary Activities",
                                                                                               "Tertiary and Quaternary Activities", "Transport and Communication", "International Trade"]),
        ("India: People and Economy", "India: People and Economy", "legy2", 1, None, ["Population: Distribution, Density, Growth and Composition", "Human Settlements",
                                                                                   "Land Resources and Agriculture", "Water Resources", "Mineral and Energy Resources",
                                                                                   "Planning and Sustainable Development in Indian Context", "Transport and Communication",
                                                                                   "International Trade", "Geographical Perspective on Selected Issues and Problems"]),
    ]),
    ("Political Science", [
        ("Contemporary World Politics", "Contemporary World Politics", "leps1", 1, None, ["The End of Bipolarity", "Contemporary Centres of Power", "Contemporary South Asia",
                                                                                       "International Organisations", "Security in the Contemporary World",
                                                                                       "Environment and Natural Resources", "Globalisation"]),
        ("Politics in India since Independence", "Politics in India since Independence", "leps2", 1, None, ["Challenges of Nation Building", "Era of One-party Dominance",
                                                                                                         "Politics of Planned Development", "India's External Relations",
                                                                                                         "Challenges to and Restoration of the Congress System",
                                                                                                         "The Crisis of Democratic Order", "Regional Aspirations",
                                                                                                         "Recent Developments in Indian Politics"]),
    ]),
    ("Psychology", [
        ("Psychology", "Psychology", "lepy1", 1, None, ["Variations in Psychological Attributes", "Self and Personality", "Meeting Life Challenges", "Psychological Disorders",
                                                     "Therapeutic Approaches", "Attitude and Social Cognition", "Social Influence and Group Processes"]),
    ]),
    ("Sociology", [
        ("Indian Society", "Indian Society", "lesy1", 1, None, ["Introducing Indian Society", "The Demographic Structure of the Indian Society",
                                                             "Social Institutions: Continuity and Change", "The Market as a Social Institution",
                                                             "Patterns of Social Inequality and Exclusion", "The Challenges of Cultural Diversity", "-Suggestions for Project Work"]),
        ("Social Change and Development in India", "Social Change and Development in India", "lesy2", 1, None, ["Structural Change", "Cultural Change",
                                                                                                             "The Constitution and Social Change",
                                                                                                             "Change and Development in Rural Society",
                                                                                                             "Change and Development in Industrial Society",
                                                                                                             "Globalisation and Social Change", "Mass Media and Communications",
                                                                                                             "Social Movements"]),
    ]),
]}
