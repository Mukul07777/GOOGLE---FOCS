"""Classes 1-12 by NCERT book, read from each book's contents pages (ncert.nic.in, 2026-27 reprints); Classes 9-12
follow the CBSE curriculum 2026-27 (its unit marks; chapters CBSE has dropped are marked "-" and left out).

A unit is (name, book, book code, first chapter number in that book, unit marks or None, chapters). A chapter is a
name, or a dict with "name" and any of "topics", "marks". Topics left out come from the chapter PDF's own section
headings (Classes 6-12), else the subject's language topics."""

E1 = "Mridang"
C1 = {"default": None, "subjects": [
    ("English", [
        ("Unit 1: My Family and Me", E1, "aemr1", 1, None, ["Two Little Hands", "Greetings"]),
        ("Unit 2: Life Around Us", E1, "aemr1", 3, None, ["Picture Time", "The Cap-seller and the Monkeys", "A Farm"]),
        ("Unit 3: Food", E1, "aemr1", 6, None, ["Fun with Pictures", "The Food we Eat"]),
        ("Unit 4: Seasons", E1, "aemr1", 8, None, ["The Four Seasons", "Anandi's Rainbow"]),
    ]),
    ("Mathematics", [
        ("Joyful Mathematics", "Joyful Mathematics", "aejm1", 1, None, [
            {"name": "Finding the Furry Cat! (Pre-number Concepts)", "topics": ["Top and bottom, near and far", "Inside, outside, above and below", "Matching and sorting things", "Big and small"]},
            {"name": "What is Long? What is Round? (Shapes)", "topics": ["Long and round things", "Things that roll and things that slide", "Shapes around us", "Sorting by shape"]},
            {"name": "Mango Treat (Numbers 1 to 9)", "topics": ["Counting objects up to 9", "Reading and writing 1 to 9", "Matching numbers to objects", "More and less"]},
            {"name": "Making 10 (Numbers 10 to 20)", "topics": ["Making a group of ten", "Numbers 10 to 20", "Counting on from 10", "Writing numbers up to 20"]},
            {"name": "How Many? (Addition and Subtraction of Single Digit Numbers)", "topics": ["Putting together: addition", "Taking away: subtraction", "Adding single-digit numbers", "Subtraction stories"]},
            {"name": "Vegetable Farm (Addition and Subtraction up to 20)", "topics": ["Adding numbers up to 20", "Subtracting numbers up to 20", "Story sums"]},
            {"name": "Lina's Family (Measurement)", "topics": ["Tall and short", "Long and short", "Heavy and light", "Measuring with hand spans and steps"]},
            {"name": "Fun with Numbers (Numbers 21 to 99)", "topics": ["Tens and ones", "Counting from 21 to 99", "Reading and writing two-digit numbers", "Number before, after and between"]},
            {"name": "Utsav (Patterns)", "topics": ["Patterns with shapes and colours", "Patterns with numbers", "Completing a pattern", "Making your own pattern"]},
            {"name": "How do I Spend my Day? (Time)", "topics": ["Morning, afternoon, evening and night", "Before and after", "Days of the week", "Longer and shorter time"]},
            {"name": "How Many Times? (Multiplication)", "topics": ["Equal groups", "Adding the same number again", "Counting in twos and fives"]},
            {"name": "How Much Can We Spend? (Money)", "topics": ["Indian coins and notes", "Counting money", "Buying and selling"]},
            {"name": "So Many Toys (Data Handling)", "topics": ["Collecting information", "Sorting and counting", "Tally marks", "Reading picture data"]},
        ]),
    ]),
    ("Hindi", [
        ("इकाई 1: परिवार", "सारंगी", "ahsr1", 1, None, ["मीना का परिवार", "दादा-दादी", "रीना का दिन", "रानी भी", "मिठाई", "तीन साथी"]),
        ("इकाई 2: जीव-जगत", "सारंगी", "ahsr1", 7, None, ["वाह, मेरे घोड़े!", "खतरे में साँप"]),
        ("इकाई 3: हमारा खान-पान", "सारंगी", "ahsr1", 9, None, ["आलू की सड़क", "झूलम-झूली", "भुट्टे", "फूली रोटी"]),
        ("इकाई 4: त्योहार और मेले", "सारंगी", "ahsr1", 13, None, ["मेला", "बरखा और मेघा", "होली"]),
        ("इकाई 5: हरी-भरी दुनिया", "सारंगी", "ahsr1", 16, None, ["जन्मदिवस पर पेड़ लगाओ", "हवा", "कितनी प्यारी है ये दुनिया", "चाँद का बच्चा"]),
    ]),
]}

C2 = {"default": None, "subjects": [
    ("English", [
        ("Unit 1: Fun with Friends", E1, "bemr1", 1, None, ["My Bicycle", "Picture Reading"]),
        ("Unit 2: Welcome to My World", E1, "bemr1", 3, None, ["It is Fun", "Seeing without Seeing"]),
        ("Unit 3: Going Places", E1, "bemr1", 5, None, ["Come Back Soon", "Between Home and School", "This is My Town"]),
        ("Unit 4: Life Around Us", E1, "bemr1", 8, None, ["A Show of Clouds", "My Name", "The Crow", "The Smart Monkey"]),
        ("Unit 5: Harmony", E1, "bemr1", 12, None, ["Little Drops of Water", "We are all Indians"]),
    ]),
    ("Mathematics", [
        ("Joyful Mathematics", "Joyful Mathematics", "bejm1", 1, None, [
            {"name": "A Day at the Beach (Counting in Groups)", "topics": ["Counting in groups of 2, 5 and 10", "Skip counting", "Estimating how many"]},
            {"name": "Shapes Around Us (3D Shapes)", "topics": ["Cube, cuboid, cylinder, cone and sphere", "Faces, edges and corners", "Shapes that roll and shapes that slide"]},
            {"name": "Fun with Numbers (Numbers 1 to 100)", "topics": ["Tens and ones up to 100", "Number names", "Comparing numbers", "Number before, after and between"]},
            {"name": "Shadow Story (Togalu) (2D Shapes)", "topics": ["Shadows of objects", "Circle, triangle, square and rectangle", "Tracing and drawing shapes"]},
            {"name": "Playing with Lines (Orientations of a Line)", "topics": ["Straight and curved lines", "Standing, sleeping and slanting lines", "Drawing with lines"]},
            {"name": "Decoration for Festival (Addition and Subtraction)", "topics": ["Adding two-digit numbers", "Subtracting two-digit numbers", "Story sums"]},
            {"name": "Rani's Gift (Measurement)", "topics": ["Measuring length with hand spans and objects", "Comparing weights", "Comparing how much a container holds"]},
            {"name": "Grouping and Sharing (Multiplication and Division)", "topics": ["Equal groups and multiplication", "Sharing equally", "Division as sharing"]},
            {"name": "Which Season is it? (Measurement of Time)", "topics": ["Seasons of the year", "Months of the year", "Reading a calendar", "Days and weeks"]},
            {"name": "Fun at the Fair (Money)", "topics": ["Coins and notes", "Adding money", "Shopping at the fair"]},
            {"name": "Data Handling", "topics": ["Collecting data", "Pictographs", "Reading tables"]},
        ]),
    ]),
    ("Hindi", [
        ("इकाई 1: परिवार", "सारंगी", "bhsr1", 1, None, ["नीमा की दादी", "घर", "माला की चाँदी की पायल", "माँ", "थाथू और मैं", "चींटा", "टिल्लू जी"]),
        ("इकाई 2: रंग ही रंग", "सारंगी", "bhsr1", 8, None, ["तीन दोस्त", "दुनिया रंग-बिरंगी", "कौन", "बैंगनी जोजो", "तोसिया का सपना"]),
        ("इकाई 3: हरी-भरी धरती", "सारंगी", "bhsr1", 13, None, ["तालाब", "बीज", "किसान", "मूली", "बरसात और मेंढक"]),
        ("इकाई 4: मित्रता", "सारंगी", "bhsr1", 18, None, ["शेर और चूहे की दोस्ती", "आउट", "छुपन-छुपाई", "हाथी साइकिल चला रहा था"]),
        ("इकाई 5: आकाश", "सारंगी", "bhsr1", 22, None, ["चार दिशाएँ", "चंदा मामा", "गिरे ताल में चंदा मामा", "सबसे बड़ा छाता", "बादल"]),
    ]),
]}

S3 = "Santoor"
C3 = {"default": None, "subjects": [
    ("English", [
        ("Unit 1: Fun with Friends", S3, "cesa1", 1, None, ["Colours", "Badal and Moti", "Best Friends"]),
        ("Unit 2: Toys and Games", S3, "cesa1", 4, None, ["Out in the Garden", "Talking Toys", "Paper Boats"]),
        ("Unit 3: Good Food", S3, "cesa1", 7, None, ["The Big Laddoo", "Thank God", "Madhu's Wish"]),
        ("Unit 4: The Sky", S3, "cesa1", 10, None, ["Night", "Chanda Mama Counts the Stars", "Chandrayaan"]),
    ]),
    ("Mathematics", [
        ("Maths Mela", "Maths Mela", "cemm1", 1, None, [
            {"name": "What's in a Name?", "topics": ["Counting by matching", "Tally marks", "Keeping a record of numbers"]},
            {"name": "Toy Joy", "topics": ["Solid shapes in toys", "Faces of solid shapes", "Flat shapes around us"]},
            {"name": "Double Century", "topics": ["Estimating a number", "The story of our numbers", "Counting up to 200", "Hundreds, tens and ones"]},
            {"name": "Vacation with My Nani Maa", "topics": ["Number tricks and games", "Adding two-digit numbers", "Subtracting two-digit numbers", "Patterns in sums"]},
            {"name": "Fun with Shapes", "topics": ["Shapes in a rangoli", "Triangles, squares and rectangles", "Sides and corners", "Making shapes with tangram pieces"]},
            {"name": "House of Hundreds – I", "topics": ["Counting beyond 200", "Hundreds, tens and ones", "Numbers up to 999"]},
            {"name": "Raksha Bandhan", "topics": ["Equal groups", "Multiplication as repeated addition", "Multiplication tables"]},
            {"name": "Fair Share", "topics": ["Sharing equally", "Halves and quarters", "Fair and unfair shares"]},
            {"name": "House of Hundreds – II", "topics": ["Estimating large numbers", "Comparing three-digit numbers", "Ordering numbers"]},
            {"name": "Fun at Class Party!", "topics": ["Measuring with hand spans", "Measuring length", "Metre and centimetre"]},
            {"name": "Filling and Lifting", "topics": ["How much a container holds", "Litre", "Heavy and light", "Kilogram"]},
            {"name": "Give and Take", "topics": ["Adding three-digit numbers", "Subtracting three-digit numbers", "Story sums"]},
            {"name": "Time Goes On", "topics": ["The calendar", "Days, weeks and months", "Reading a clock"]},
            {"name": "The Surajkund Fair", "topics": ["Things that look the same on both sides", "Patterns at the fair", "Money and shopping"]},
        ]),
    ]),
    ("Hindi", [
        ("इकाई 1: हमारा पर्यावरण", "वीणा", "chve1", 1, None, ["सीखो", "चींटी", "कितने पैर?", "बया हमारी चिड़िया रानी!", "आम का पेड़"]),
        ("इकाई 2: हमारे मित्र", "वीणा", "chve1", 6, None, ["बीरबल की खिचड़ी", "मित्र को पत्र", "चतुर गीदड़", "प्रकृति पर्व — फूलदेई"]),
        ("इकाई 3: आओ खेलें", "वीणा", "chve1", 10, None, ["रस्साकशी", "एक जादुई पिटारा"]),
        ("इकाई 4: अपना-अपना काम", "वीणा", "chve1", 12, None, ["अपना-अपना काम", "पेड़ों की अम्मा 'तिमक्का'", "किसान की होशियारी"]),
        ("इकाई 5: हमारा देश", "वीणा", "chve1", 15, None, ["भारत", "चंद्रयान (संवाद)", "बोलने वाली माँद", "हम अनेक किंतु एक"]),
    ]),
    ("The World Around Us", [
        ("Unit 1: Our Families and Communities", "Our Wondrous World", "ceev1", 1, None, [
            {"name": "Family and Friends", "topics": ["My family", "Family members and relationships", "Friends and neighbours", "Helping each other"]},
            {"name": "Going to the Mela", "topics": ["A visit to the mela", "Things we see at a mela", "Getting to the mela"]},
            {"name": "Celebrating Festivals", "topics": ["Festivals we celebrate", "Food, clothes and customs", "Festivals bring people together"]},
        ]),
        ("Unit 2: Life Around Us", "Our Wondrous World", "ceev1", 4, None, [
            {"name": "Getting to Know Plants", "topics": ["Parts of a plant", "Trees, shrubs and herbs", "Leaves of different shapes"]},
            {"name": "Plants and Animals Live Together", "topics": ["Animals that live on plants", "Life in the soil", "Homes of animals"]},
            {"name": "Living in Harmony", "topics": ["Caring for plants and animals", "Living together in nature"]},
        ]),
        ("Unit 3: Gifts of Nature", "Our Wondrous World", "ceev1", 7, None, [
            {"name": "Water — A Precious Gift", "topics": ["Uses of water", "Where water comes from", "Saving water"]},
            {"name": "Food We Eat", "topics": ["Food from plants and animals", "Cooking and eating together", "Healthy food"]},
            {"name": "Staying Healthy and Happy", "topics": ["Clean habits", "Exercise and play", "Feeling happy"]},
        ]),
        ("Unit 4: Things Around Us", "Our Wondrous World", "ceev1", 10, None, [
            {"name": "This World of Things", "topics": ["Things around us", "Materials things are made from", "Sorting things"]},
            {"name": "Making Things", "topics": ["How things are made", "Making things from waste", "Crafts around us"]},
            {"name": "Taking Charge of Waste", "topics": ["Waste around us", "Reduce, reuse and recycle", "Keeping our surroundings clean"]},
        ]),
    ]),
]}

C4 = {"default": None, "subjects": [
    ("English", [
        ("Unit 1: My Land", S3, "desa1", 1, None, ["Together We Can", "The Tinkling Bells", "Be Smart, Be Safe"]),
        ("Unit 2: My Beautiful World", S3, "desa1", 4, None, ["One Thing at a Time", "The Old Stag", "Braille"]),
        ("Unit 3: Fun with Games", S3, "desa1", 7, None, ["Fit Body, Fit Mind, Fit Nation", "The Lagori Champions", "Hekko"]),
        ("Unit 4: Up High", S3, "desa1", 10, None, ["The Swing", "A Journey to the Magical Mountains", "Maheshwar"]),
    ]),
    ("Mathematics", [
        ("Maths Mela", "Maths Mela", "demm1", 1, None, [
            {"name": "Shapes Around Us", "topics": ["Solid shapes in buildings", "Faces, edges and corners", "Making models with blocks"]},
            {"name": "Hide and Seek", "topics": ["What can be seen from a place", "Top, front and side views", "Positions on a map"]},
            {"name": "Pattern Around Us", "topics": ["Counting by grouping", "Patterns in numbers", "Patterns in shapes"]},
            {"name": "Thousands Around Us", "topics": ["Numbers up to 10,000", "Place value", "Comparing and ordering numbers", "Adding and subtracting large numbers"]},
            {"name": "Sharing and Measuring", "topics": ["Parts and wholes", "Halves, thirds and quarters", "Fractions of a collection", "Measuring with fractions"]},
            {"name": "Measuring Length", "topics": ["Length, height, width and depth", "Centimetre and metre", "Measuring and estimating length"]},
            {"name": "The Cleanest Village", "topics": ["Money", "Adding and subtracting money", "Planning a trip"]},
            {"name": "Weigh it, Pour it", "topics": ["Grams and kilograms", "Millilitres and litres", "Comparing weights and capacities"]},
            {"name": "Equal Groups", "topics": ["Equal groups and multiplication", "Multiples", "Multiplication tables"]},
            {"name": "Elephants, Tigers, and Leopards", "topics": ["Number games with a target", "Ways to add and subtract", "Reading data about animals"]},
            {"name": "Fun with Symmetry", "topics": ["Line of symmetry", "Symmetrical shapes", "Making symmetrical patterns"]},
            {"name": "Ticking Clocks and Turning Calendar", "topics": ["Reading a clock", "Hours and minutes", "The calendar and leap years"]},
            {"name": "The Transport Museum", "topics": ["Multiplying two-digit numbers", "Division", "Puzzles with products"]},
            {"name": "Data Handling", "topics": ["Asking the right question", "Collecting and organising data", "Tables and pictographs", "Bar graphs"]},
        ]),
    ]),
    ("Hindi", [
        ("वीणा", "वीणा", "dhve1", 1, None, ["चिड़िया का गीत", "बगीचे का घोंघा", "नीम", "हमारा आहार", "आसमान गिरा", "जयपुर से पत्र", "नकली हीरे",
                                         "ओणम के रंग", "मिठाइयों का सम्मेलन", "कैमरा", "कविता का कमाल", "शतरंज में मात", "हमारा आदित्य"]),
    ]),
    ("The World Around Us", [
        ("Unit 1: Our Community", "Our Wondrous World", "deev1", 1, None, [
            {"name": "Living Together", "topics": ["Our community", "People who help us", "Sharing and caring"]},
            {"name": "Exploring Our Neighbourhood", "topics": ["Places in our neighbourhood", "Drawing a map of the neighbourhood", "Public places and their care"]},
        ]),
        ("Unit 2: Life Around Us", "Our Wondrous World", "deev1", 3, None, [
            {"name": "Nature Trail", "topics": ["Safety rules on a trail", "Bird diary", "Tiny animals", "Leaf autograph"]},
            {"name": "Growing up with Nature", "topics": ["Seeds and growing plants", "Animals and their young", "Caring for nature"]},
        ]),
        ("Unit 3: Health and Well-being", "Our Wondrous World", "deev1", 5, None, [
            {"name": "Food for Health", "topics": ["A balanced meal", "Food groups", "Healthy eating habits"]},
            {"name": "Happy and Healthy Living", "topics": ["Exercise and yoga", "Rest and sleep", "Keeping clean"]},
        ]),
        ("Unit 4: Things Around Us", "Our Wondrous World", "deev1", 7, None, [
            {"name": "How Things Work", "topics": ["Tools and simple machines at home", "Wheels and levers", "How tools help us"]},
            {"name": "How Things are Made", "topics": ["Raw materials", "From farm to factory", "Handmade and machine-made things"]},
        ]),
        ("Unit 5: Our Environment", "Our Wondrous World", "deev1", 9, None, [
            {"name": "Different Lands, Different Lives", "topics": ["Deserts, mountains and coasts", "How people live in different lands", "Houses, food and clothes"]},
            {"name": "Our Sky", "topics": ["The Sun, the Moon and the stars", "Day and night", "Watching the sky"]},
        ]),
    ]),
]}

C5 = {"default": None, "subjects": [
    ("English", [
        ("Unit 1: Let's Have Fun", S3, "eesa1", 1, None, ["Papa's Spectacles", "Gone with the Scooter"]),
        ("Unit 2: My Colourful World", S3, "eesa1", 3, None, ["The Rainbow", "The Wise Parrot"]),
        ("Unit 3: Water", S3, "eesa1", 5, None, ["The Frog", "What a Tank!"]),
        ("Unit 4: Ups and Downs", S3, "eesa1", 7, None, ["Gilli Danda", "The Decision of the Panchayat"]),
        ("Unit 5: Work is Worship", S3, "eesa1", 9, None, ["Vocation", "Glass Bangles"]),
    ]),
    ("Mathematics", [
        ("Maths Mela", "Maths Mela", "eemm1", 1, None, [
            {"name": "We the Travellers — I", "topics": ["Large numbers", "Place value up to lakhs", "Reading and writing large numbers"]},
            {"name": "Fractions", "topics": ["Fractions of a whole", "Comparing fractions", "Equivalent fractions"]},
            {"name": "Angles as Turns", "topics": ["Full, half and quarter turns", "Angles", "Right angles"]},
            {"name": "We the Travellers — II", "topics": ["Adding and subtracting large numbers", "Making sums equal", "Estimating sums"]},
            {"name": "Far and Near", "topics": ["Units of length", "Kilometre, metre and centimetre", "Converting between units"]},
            {"name": "The Dairy Farm", "topics": ["Multiplication", "Arrangements in rows and columns", "Story sums"]},
            {"name": "Shapes and Patterns", "topics": ["Weaving patterns", "Patterns with shapes", "Tiling"]},
            {"name": "Weight and Capacity", "topics": ["Grams and kilograms", "Millilitres and litres", "Estimating weight and capacity"]},
            {"name": "Coconut Farm", "topics": ["Division facts", "Dividend, divisor, quotient and remainder", "Long division"]},
            {"name": "Symmetrical Designs", "topics": ["Reflection symmetry", "Lines of symmetry", "Rotational symmetry"]},
            {"name": "Grandmother's Quilt", "topics": ["Perimeter", "Area", "Squares and rectangles"]},
            {"name": "Racing Seconds", "topics": ["Reading time", "How long something takes", "Seconds, minutes and hours"]},
            {"name": "Animal Jumps", "topics": ["Multiples", "Factors", "Number patterns"]},
            {"name": "Maps and Locations", "topics": ["Directions", "Reading a map", "Scale and distance"]},
            {"name": "Data Through Pictures", "topics": ["Collecting data", "Pictographs", "Bar graphs"]},
        ]),
    ]),
    ("Hindi", [
        ("वीणा", "वीणा", "ehve1", 1, None, ["किरन", "न्याय की कुर्सी", "चाँद का कुरता", "साङकेन", "सुंदरिया", "चतुर चित्रकार", "मेरा बचपन",
                                         "काज़ीरंगा राष्ट्रीय उद्यान की यात्रा", "न्याय", "तीन मछलियाँ", "हमारे ये कलामंदिर", "गंगा की कहानी"]),
    ]),
    ("The World Around Us", [
        ("Unit 1: Life Around Us", "Our Wondrous World", "eeev1", 1, None, [
            {"name": "Water — The Essence of Life", "topics": ["Water for life", "Sources of water", "Saving water"]},
            {"name": "Journey of a River", "topics": ["From the mountains to the sea", "Life along a river", "Keeping rivers clean"]},
        ]),
        ("Unit 2: Health and Well-being", "Our Wondrous World", "eeev1", 3, None, [
            {"name": "The Mystery of Food", "topics": ["What our food gives us", "Where food comes from", "Keeping food from spoiling"]},
            {"name": "Our School — A Happy Place", "topics": ["Our school", "Safety at school", "Friendship and kindness"]},
        ]),
        ("Unit 3: Incredible India", "Our Wondrous World", "eeev1", 5, None, [
            {"name": "Our Vibrant Country", "topics": ["Republic Day celebrations", "The diversity of India", "Finding India in currency notes"]},
            {"name": "Some Unique Places", "topics": ["Unique places of India", "Heritage sites", "Travel and maps"]},
        ]),
        ("Unit 4: Things Around Us", "Our Wondrous World", "eeev1", 7, None, [
            {"name": "Energy — How Things Work", "topics": ["Forms of energy", "Energy at home", "Saving energy"]},
            {"name": "Clothes — How Things are Made", "topics": ["From fibre to fabric", "Clothes for different seasons", "Weaving and dyeing"]},
        ]),
        ("Unit 5: Our Amazing Planet", "Our Wondrous World", "eeev1", 9, None, [
            {"name": "Rhythms of Nature", "topics": ["Day and night", "Seasons", "Cycles in nature"]},
            {"name": "Earth — Our Shared Home", "topics": ["Living things share the Earth", "Protecting the environment", "What we can do"]},
        ]),
    ]),
]}

P6, P7, P8 = "Poorvi", "Poorvi", "Poorvi"
C6 = {"default": None, "subjects": [
    ("English", [
        ("Unit 1: Fables and Folk Tales", P6, "fepr1", 1, None, ["A Bottle of Dew", "The Raven and the Fox", "Rama to the Rescue"]),
        ("Unit 2: Friendship", P6, "fepr1", 2, None, ["The Unlikely Best Friends", "A Friend's Prayer", "The Chair"]),
        ("Unit 3: Nurturing Nature", P6, "fepr1", 3, None, ["Neem Baba", "What a Bird Thought", "Spices that Heal Us"]),
        ("Unit 4: Sports and Wellness", P6, "fepr1", 4, None, ["Change of Heart", "The Winner", "Yoga — A Way of Life"]),
        ("Unit 5: Culture and Tradition", P6, "fepr1", 5, None, ["Hamara Bharat — Incredible India!", "The Kites", "Ila Sachani: Embroidering Dreams with her Feet", "National War Memorial"]),
    ]),
    ("Mathematics", [
        ("Ganita Prakash", "Ganita Prakash", "fegp1", 1, None, ["Patterns in Mathematics", "Lines and Angles", "Number Play", "Data Handling and Presentation", "Prime Time",
                                                             "Perimeter and Area", "Fractions", "Playing with Constructions", "Symmetry", "The Other Side of Zero"]),
    ]),
    ("Science", [
        ("Curiosity", "Curiosity", "fecu1", 1, None, ["The Wonderful World of Science", "Diversity in the Living World", "Mindful Eating: A Path to a Healthy Body",
                                                  "Exploring Magnets", "Measurement of Length and Motion", "Materials Around Us", "Temperature and its Measurement",
                                                  "A Journey through States of Water", "Methods of Separation in Everyday Life",
                                                  "Living Creatures: Exploring their Characteristics", "Nature's Treasures", "Beyond Earth"]),
    ]),
    ("Social Science", [
        ("India and the World: Land and the People", "Exploring Society: India and Beyond", "fees1", 1, None, ["Locating Places on the Earth", "Oceans and Continents", "Landforms and Life"]),
        ("Tapestry of the Past", "Exploring Society: India and Beyond", "fees1", 4, None, ["Timeline and Sources of History", "India, That Is Bharat", "The Beginnings of Indian Civilisation"]),
        ("Our Cultural Heritage and Knowledge Traditions", "Exploring Society: India and Beyond", "fees1", 7, None, ["India's Cultural Roots", "Unity in Diversity, or 'Many in the One'"]),
        ("Governance and Democracy", "Exploring Society: India and Beyond", "fees1", 9, None, ["Family and Community", "Grassroots Democracy — Part 1: Governance",
                                                                                           "Grassroots Democracy — Part 2: Local Government in Rural Areas",
                                                                                           "Grassroots Democracy — Part 3: Local Government in Urban Areas"]),
        ("Economic Life Around Us", "Exploring Society: India and Beyond", "fees1", 13, None, ["The Value of Work", "Economic Activities Around Us"]),
    ]),
    ("Hindi", [
        ("मल्हार", "मल्हार", "fhml1", 1, None, ["मातृभूमि", "गोल", "पहली बूँद", "हार की जीत", "रहीम के दोहे", "मेरी माँ", "जलाते चलो", "सत्रिया और बिहू नृत्य",
                                           "मैया मैं नहिं माखन खायो", "परीक्षा", "चेतक की वीरता", "हिंद महासागर में छोटा-सा हिंदुस्तान", "पेड़ की बात"]),
    ]),
    ("Sanskrit", [
        ("दीपकम्", "दीपकम्", "fsde1", 1, None, ["वयं वर्णमालां पठामः", "संयुक्त-व्यञ्जनानि", "एषः कः? एषा का? एतत् किम्?", "अहं च त्वं च", "संख्यागणना ननु सरला",
                                            "अहं प्रातः उत्तिष्ठामि", "शूराः वयं धीराः वयम्", "सः एव महान् चित्रकारः", "अतिथिदेवो भव", "बुद्धिः सर्वार्थसाधिका",
                                            "यः जानाति सः पण्डितः", "त्वम् आपणं गच्छ", "पृथिव्यां त्रीणि रत्नानि", "आलस्यं हि मनुष्याणां शरीरस्थः महान् रिपुः",
                                            "माधवस्य प्रियम् अङ्गम्", "वृक्षाः सत्पुरुषाः इव"]),
    ]),
]}

C7 = {"default": None, "subjects": [
    ("English", [
        ("Unit 1: Learning Together", P7, "gepr1", 1, None, ["The Day the River Spoke", "Try Again", "Three Days to See"]),
        ("Unit 2: Wit and Humour", P7, "gepr1", 2, None, ["Animals, Birds, and Dr. Dolittle", "A Funny Man", "Say the Right Thing"]),
        ("Unit 3: Dreams and Discoveries", P7, "gepr1", 3, None, ["My Brother's Great Invention", "Paper Boats", "North, South, East, West"]),
        ("Unit 4: Travel and Adventure", P7, "gepr1", 4, None, ["The Tunnel", "Travel", "Conquering the Summit"]),
        ("Unit 5: Bravehearts", P7, "gepr1", 5, None, ["A Homage to Our Brave Soldiers", "My Dear Soldiers", "Rani Abbakka"]),
    ]),
    ("Mathematics", [
        ("Ganita Prakash Part I", "Ganita Prakash Part I", "gegp1", 1, None, ["Large Numbers Around Us", "Arithmetic Expressions", "A Peek Beyond the Point",
                                                                          "Expressions using Letter-Numbers", "Parallel and Intersecting Lines", "Number Play",
                                                                          "A Tale of Three Intersecting Lines", "Working with Fractions"]),
        ("Ganita Prakash Part II", "Ganita Prakash Part II", "gegp2", 1, None, ["Geometric Twins", "Operations with Integers", "Finding Common Ground",
                                                                            "Another Peek Beyond the Point", "Connecting the Dots...", "Constructions and Tilings",
                                                                            "Finding the Unknown"]),
    ]),
    ("Science", [
        ("Curiosity", "Curiosity", "gecu1", 1, None, ["The Ever-Evolving World of Science", "Exploring Substances: Acidic, Basic, and Neutral",
                                                  "Electricity: Circuits and their Components", "The World of Metals and Non-metals",
                                                  "Changes Around Us: Physical and Chemical", "Adolescence: A Stage of Growth and Change",
                                                  "Heat Transfer in Nature", "Measurement of Time and Motion", "Life Processes in Animals",
                                                  "Life Processes in Plants", "Light: Shadows and Reflections", "Earth, Moon, and the Sun"]),
    ]),
    ("Social Science", [
        ("India and the World: Land and the People", "Exploring Society Part I", "gees1", 1, None, ["Geographical Diversity of India", "Understanding the Weather", "Climates of India"]),
        ("India and the World: Land and the People", "Exploring Society Part II", "gees2", 1, None, ["The Story of Indian Farming", "India and Her Neighbours"]),
        ("Tapestry of the Past", "Exploring Society Part I", "gees1", 4, None, ["New Beginnings: Cities and States", "The Rise of Empires", "The Age of Reorganisation",
                                                                              "The Gupta Era: An Age of Tireless Creativity"]),
        ("Tapestry of the Past", "Exploring Society Part II", "gees2", 3, None, ["Empires and Kingdoms: 6th to 10th Centuries", "Turning Tides: 11th and 12th Centuries"]),
        ("Our Cultural Heritage and Knowledge Traditions", "Exploring Society Part I", "gees1", 8, None, ["How the Land Becomes Sacred"]),
        ("Our Cultural Heritage and Knowledge Traditions", "Exploring Society Part II", "gees2", 5, None, ["India, a Home to Many"]),
        ("Governance and Democracy", "Exploring Society Part I", "gees1", 9, None, ["From the Rulers to the Ruled: Types of Governments", "The Constitution of India — An Introduction"]),
        ("Governance and Democracy", "Exploring Society Part II", "gees2", 6, None, ["The State, the Government, and You"]),
        ("Economic Life Around Us", "Exploring Society Part I", "gees1", 11, None, ["From Barter to Money", "Understanding Markets"]),
        ("Economic Life Around Us", "Exploring Society Part II", "gees2", 7, None, ["Infrastructure: Engine of India's Development", "Banks and the Magic of Finance"]),
    ]),
    ("Hindi", [
        ("मल्हार", "मल्हार", "ghml1", 1, None, ["माँ, कह एक कहानी", "तीन बुद्धिमान", "फूल और काँटा", "पानी रे पानी", "नहीं होना बीमार", "गिरिधर कविराय की कुंडलिया",
                                           "वर्षा-बहार", "बिरजू महाराज से साक्षात्कार", "चिड़िया", "मीरा के पद"]),
    ]),
    ("Sanskrit", [
        ("दीपकम्", "दीपकम्", "gsde1", 1, None, ["वन्दे भारतमातरम्", "नित्यं पिबामः सुभाषितरसम्", "मित्राय नमः", "न लभ्यते चेत् आम्लं द्राक्षाफलम्", "सेवा हि परमो धर्मः",
                                            "क्रीडाम वयं श्लोकान्त्याक्षरीम्", "ईशावास्यम् इदं सर्वम्", "हितं मनोहारि च दुर्लभं वचः", "अन्नाद् भवन्ति भूतानि",
                                            "दशमः कः?", "द्वीपेषु रम्यः द्वीपोऽण्डमानः", "वीराङ्गना पन्नाधाया"]),
    ]),
]}

C8 = {"default": None, "subjects": [
    ("English", [
        ("Unit 1: Wit and Wisdom", P8, "hepr1", 1, None, ["The Wit that Won Hearts", "A Concrete Example", "Wisdom Paves the Way"]),
        ("Unit 2: Values and Dispositions", P8, "hepr1", 2, None, ["A Tale of Valour: Major Somnath Sharma and the Battle of Badgam", "Somebody's Mother",
                                                                "Verghese Kurien — I Too Had A Dream"]),
        ("Unit 3: Mystery and Magic", P8, "hepr1", 3, None, ["The Case of the Fifth Word", "The Magic Brush of Dreams", "Spectacular Wonders"]),
        ("Unit 4: Environment", P8, "hepr1", 4, None, ["The Cherry Tree", "Harvest Hymn", "Waiting for the Rain"]),
        ("Unit 5: Science and Curiosity", P8, "hepr1", 5, None, ["Feathered Friend", "Magnifying Glass",
                                                              "Bibha Chowdhuri: The Beam of Light that Lit the Path for Women in Indian Science"]),
    ]),
    ("Mathematics", [
        ("Ganita Prakash Part I", "Ganita Prakash Part I", "hegp1", 1, None, ["A Square and A Cube", "Power Play", "A Story of Numbers", "Quadrilaterals", "Number Play",
                                                                          "We Distribute, Yet Things Multiply", "Proportional Reasoning – 1"]),
        ("Ganita Prakash Part II", "Ganita Prakash Part II", "hegp2", 1, None, ["Fractions in Disguise", "The Baudhayana-Pythagoras Theorem", "Proportional Reasoning – 2",
                                                                            "Exploring Some Geometric Themes", "Tales by Dots and Lines", "Algebra Play", "Area"]),
    ]),
    ("Science", [
        ("Curiosity", "Curiosity", "hecu1", 1, None, ["Exploring the Investigative World of Science", "The Invisible Living World: Beyond Our Naked Eye",
                                                  "Health: The Ultimate Treasure", "Electricity: Magnetic and Heating Effects", "Exploring Forces",
                                                  "Pressure, Winds, Storms, and Cyclones", "Particulate Nature of Matter",
                                                  "Nature of Matter: Elements, Compounds, and Mixtures", "The Amazing World of Solutes, Solvents, and Solutions",
                                                  "Light: Mirrors and Lenses", "Keeping Time with the Skies", "How Nature Works in Harmony",
                                                  "Our Home: Earth, a Unique Life Sustaining Planet"]),
    ]),
    ("Social Science", [
        ("India and the World: Land and the People", "Exploring Society Part I", "hees1", 1, None, ["Natural Resources and Their Use"]),
        ("India and the World: Land and the People", "Exploring Society Part II", "hees2", 1, None, ["World Geography: Some Glimpses"]),
        ("Tapestry of the Past", "Exploring Society Part I", "hees1", 2, None, ["Reshaping India's Political Map", "The Rise of the Marathas", "The Colonial Era in India"]),
        ("Tapestry of the Past", "Exploring Society Part II", "hees2", 2, None, ["India's Long Road to Independence"]),
        ("Our Cultural Heritage and Knowledge Traditions", "Exploring Society Part II", "hees2", 3, None, ["A Journey Through Indian Architecture"]),
        ("Governance and Democracy", "Exploring Society Part I", "hees1", 5, None, ["Universal Franchise and India's Electoral System",
                                                                                  "The Parliamentary System: Legislature and Executive"]),
        ("Governance and Democracy", "Exploring Society Part II", "hees2", 4, None, ["The Role of the Judiciary in Our Society", "Citizenship: Rights and Duties"]),
        ("Economic Life Around Us", "Exploring Society Part I", "hees1", 7, None, ["Factors of Production"]),
        ("Economic Life Around Us", "Exploring Society Part II", "hees2", 6, None, ["Dynamics of Population", "India's Urban Landscape"]),
        ("Our Cultural Heritage and Knowledge Traditions", "Exploring Society Part II", "hees2", 8, None, ["Cultural Currents: 13th to 17th Centuries"]),
    ]),
    ("Hindi", [
        ("मल्हार", "मल्हार", "hhml1", 1, None, ["स्वदेश", "दो गौरैया", "एक आशीर्वाद", "हरिद्वार", "कबीर के दोहे", "एक टोकरी भर मिट्टी", "मत बाँधो", "नए मेहमान",
                                           "आदमी का अनुपात", "तरुण के स्वप्न"]),
    ]),
    ("Sanskrit", [
        ("दीपकम्", "दीपकम्", "hsde1", 1, None, ["संगच्छध्वं संवदध्वम्", "अल्पानामपि वस्तूनां संहतिः कार्यसाधिका", "सुभाषितरसं पीत्वा जीवनं सफलं कुरु",
                                            "प्रणम्यो देशभक्तोऽयं गोपबन्धुर्महामनाः", "गीता सुगीता कर्तव्या", "डिजिभारतम् - युगपरिवर्तनम्",
                                            "मञ्जुलमञ्जूषा सुन्दरसुरभाषा", "पश्यत कोणमैशान्यं भारतस्य मनोहरम्", "कोऽरुक्? कोऽरुक्? कोऽरुक्?",
                                            "सन्निमित्ते वरं त्यागः (क-भागः)", "सन्निमित्ते वरं त्यागः (ख-भागः)", "सम्यग्वर्णप्रयोगेण ब्रह्मलोके महीयते",
                                            "वर्णोच्चारण-शिक्षा १"]),
    ]),
]}

# Class 9: the new books of 2026-27; marks from the CBSE curriculum (Science by chapter number, Mathematics by unit)
C9 = {"default": ["English", "Hindi", "Mathematics", "Science", "Social Science"], "subjects": [
    ("English", [
        ("Kaveri", "Kaveri", "iebe1", 1, None, ["How I Taught My Grandmother to Read", "Bharat Our Land", "The Pot Maker", "Gifts of Grace: Honouring Our Vocations",
                                            "Winds of Change", "Canvas of Soil", "Vitamin-M", "I Cannot Remember My Mother",
                                            "The World of Limitless Possibilities", "Nine Gold Medals", "Twin Melodies", "A Friend Found in Music",
                                            "Carrier of Words", "Words", "Follow That Dream", "Believe in Yourself"]),
    ]),
    ("Mathematics", [
        ("Ganita Manjari Part I", "Ganita Manjari Part I", "iemh1", 1, None, [
            {"name": "Orienting Yourself: The Use of Coordinates", "marks": 4},
            {"name": "Introduction to Linear Polynomials", "marks": 5},
            {"name": "The World of Numbers", "marks": 7},
            {"name": "Exploring Algebraic Identities", "marks": 5},
            {"name": "I'm Up and Down, and Round and Round", "marks": 8.3},
            {"name": "Measuring Space: Perimeter and Area", "marks": 7},
            {"name": "The Mathematics of Maybe: Introduction to Probability", "marks": 5},
            {"name": "Predicting What Comes Next: Exploring Sequences and Progressions", "marks": 5},
        ]),
        ("Ganita Manjari Part II", "Ganita Manjari Part II", "iemh2", 1, None, [
            {"name": "Propositions and their Converses", "marks": 8.3},
            {"name": "How Quantities Combine: Understanding Data", "marks": 5},
            {"name": "The World of Algorithms"},
            {"name": "Quadrilaterals", "marks": 8.3},
            {"name": "Two Variables, One Line", "marks": 5},
            {"name": "Math of Space: Surface Area and Volume", "marks": 7},
        ]),
    ]),
    ("Science", [
        ("Exploration", "Exploration", "iesc1", 1, None, [
            {"name": "Exploration: Entering the World of Secondary Science"},
            {"name": "Cell: The Building Block of Life", "marks": 6.75}, {"name": "Tissues in Action", "marks": 6.75},
            {"name": "Describing Motion Around Us", "marks": 5.75}, {"name": "Exploring Mixtures and their Separation", "marks": 8.33},
            {"name": "How Forces Affect Motion", "marks": 5.75}, {"name": "Work, Energy, and Simple Machines", "marks": 5.75},
            {"name": "Journey Inside the Atom", "marks": 8.33}, {"name": "Atomic Foundations of Matter", "marks": 8.33},
            {"name": "Sound Waves: Characteristics and Applications", "marks": 5.75},
            {"name": "Reproduction: How Life Continues", "marks": 6.75}, {"name": "Patterns in Life: Diversity and Classification", "marks": 6.75},
            {"name": "Earth as a System: Energy, Matter, and Life", "marks": 5},
        ]),
    ]),
    ("Social Science", [
        ("Understanding Society Part I", "Understanding Society: India and Beyond Part I", "iest1", 1, None, [
            "Understanding Social Science", "Shaping of the Earth's Surface", "Atmosphere and Climate", "Early Humans and Beginning of Civilisation",
            "State and Society up to 1000 CE", "Democracy", "Elections", "Building Blocks in Economics: The Problem of Choice",
            "The Price Puzzle: What Drives the Market"]),
        ("Understanding Society Part II", "Understanding Society: India and Beyond Part II", "iest2", 1, None, [
            "Oceans and Life", "Life on Earth", "Resistance and Resilience (1000–1700 CE)", "Governance and Public Policy",
            "Managing Your Personal Finances", "From Ideas to Startups"]),
    ]),
    ("Hindi", [
        ("गद्य खंड", "गंगा", "ihga1", 1, None, ["दो बैलों की कथा", "क्या लिखूँ?", "संवादहीन", "ऐसी भी बातें होती हैं", "आखिरी चट्टान तक", "रीढ़ की हड्डी", "मैं और मेरा देश"]),
        ("काव्य खंड", "गंगा", "ihga1", 8, None, ["पद (रैदास)", "राम-लक्ष्मण-परशुराम संवाद", "भारति, जय, विजय करे!", "झाँसी की रानी", "घर की याद"]),
    ]),
    ("Sanskrit", [
        ("शारदा", "शारदा", "ihsh1", 1, None, ["सत्यं शिवं सुन्दरं संस्कृतम्", "सुखस्य मूलं धर्मः धर्मस्य मूलम् अर्थः", "आत्मवत्सर्वभूतेषु यः पश्यति सः पण्डितः",
                                          "न खलु वयस्तेजसो हेतुः", "एषा सा कृतकबुद्धिः मानवबुद्धेः सहकरी", "मनःपूतं समाचरेत्",
                                          "उपायं चिन्तयेत् प्राज्ञस्तथापायं च चिन्तयेत्", "अन्नाद् आनन्दं प्रति", "कृतं प्रतिकृतं भूयादेष धर्मः सनातनः",
                                          "णमो अरिहन्ताणम्", "वर्णोच्चारण-शिक्षा २"]),
    ]),
]}

# Class 10: CBSE 2026-27 marks by unit; "The Age of Industrialisation" is tested only in school (periodic tests)
C10 = {"default": ["English", "Hindi Course A", "Mathematics", "Science", "Social Science"], "subjects": [
    ("English", [
        ("First Flight", "First Flight", "jeff1", 0, None, ["A Letter to God", "Dust of Snow", "Fire and Ice", "Nelson Mandela: Long Walk to Freedom", "A Tiger in the Zoo",
                                                         "Two Stories about Flying", "How to Tell Wild Animals", "The Ball Poem", "From the Diary of Anne Frank", "Amanda!",
                                                         "Glimpses of India", "The Trees", "Mijbil the Otter", "Fog", "Madam Rides the Bus",
                                                         "The Tale of Custard the Dragon", "The Sermon at Benares", "For Anne Gregory", "The Proposal"]),
        ("Footprints without Feet", "Footprints without Feet", "jefp1", 0, None, ["A Triumph of Surgery", "The Thief's Story", "The Midnight Visitor", "A Question of Trust",
                                                                               "Footprints without Feet", "The Making of a Scientist", "The Necklace", "Bholi",
                                                                               "The Book That Saved the Earth"]),
    ]),
    ("Mathematics", [
        ("Number Systems", "Mathematics", "jemh1", 1, 6, ["Real Numbers"]),
        ("Algebra", "Mathematics", "jemh1", 2, 20, ["Polynomials", "Pair of Linear Equations in Two Variables", "Quadratic Equations", "Arithmetic Progressions"]),
        ("Geometry", "Mathematics", "jemh1", 6, None, [{"name": "Triangles", "marks": 7.5}]),
        ("Coordinate Geometry", "Mathematics", "jemh1", 7, 6, ["Coordinate Geometry"]),
        ("Trigonometry", "Mathematics", "jemh1", 8, 12, ["Introduction to Trigonometry", "Some Applications of Trigonometry"]),
        ("Geometry", "Mathematics", "jemh1", 10, None, [{"name": "Circles", "marks": 7.5}]),
        ("Mensuration", "Mathematics", "jemh1", 11, 10, ["Areas Related to Circles", "Surface Areas and Volumes"]),
        ("Statistics and Probability", "Mathematics", "jemh1", 13, 11, ["Statistics", "Probability"]),
    ]),
    ("Science", [
        ("Chemical Substances: Nature and Behaviour", "Science", "jesc1", 1, 25, ["Chemical Reactions and Equations", "Acids, Bases and Salts", "Metals and Non-metals",
                                                                                "Carbon and its Compounds"]),
        ("World of Living", "Science", "jesc1", 5, 25, ["Life Processes", "Control and Coordination", "How do Organisms Reproduce?", "Heredity"]),
        ("Natural Phenomena", "Science", "jesc1", 9, 12, ["Light — Reflection and Refraction", "The Human Eye and the Colourful World"]),
        ("Effects of Current", "Science", "jesc1", 11, 13, ["Electricity", "Magnetic Effects of Electric Current"]),
        ("Natural Resources", "Science", "jesc1", 13, 5, ["Our Environment"]),
    ]),
    ("Social Science", [
        ("History: India and the Contemporary World II", "India and the Contemporary World II", "jess3", 1, None, [
            {"name": "The Rise of Nationalism in Europe", "marks": 6}, {"name": "Nationalism in India", "marks": 6},
            {"name": "The Making of a Global World", "marks": 4}, {"name": "The Age of Industrialisation", "marks": 1.5},
            {"name": "Print Culture and the Modern World", "marks": 4}]),
        ("Geography: Contemporary India II", "Contemporary India II", "jess1", 1, 20, ["Resources and Development", "Forest and Wildlife Resources", "Water Resources",
                                                                                      "Agriculture", "Minerals and Energy Resources", "Manufacturing Industries",
                                                                                      "Lifelines of National Economy"]),
        ("Political Science: Democratic Politics II", "Democratic Politics II", "jess4", 1, 20, ["Power-sharing", "Federalism", "Gender, Religion and Caste", "Political Parties",
                                                                                                "Outcomes of Democracy"]),
        ("Economics: Understanding Economic Development", "Understanding Economic Development", "jess2", 1, 20, ["Development", "Sectors of the Indian Economy", "Money and Credit",
                                                                                                                "Globalisation and the Indian Economy", "Consumer Rights"]),
    ]),
    ("Hindi Course A", [
        ("क्षितिज भाग 2", "क्षितिज भाग 2", "jhks1", 1, None, ["सूरदास के पद", "राम-लक्ष्मण-परशुराम संवाद", "आत्मकथ्य", "उत्साह और अट नहीं रही है", "यह दंतुरित मुसकान और फसल",
                                                         "संगतकार", "नेताजी का चश्मा", "बालगोबिन भगत", "लखनवी अंदाज़", "एक कहानी यह भी", "नौबतखाने में इबादत", "संस्कृति"]),
        ("कृतिका भाग 2", "कृतिका भाग 2", "jhkr1", 1, None, ["माता का अँचल", "साना-साना हाथ जोड़ि", "मैं क्यों लिखता हूँ?"]),
    ]),
    ("Hindi Course B", [
        ("स्पर्श भाग 2", "स्पर्श भाग 2", "jhsp1", 1, None, ["साखी", "पद (मीरा)", "मनुष्यता", "पर्वत प्रदेश में पावस", "तोप", "कर चले हम फ़िदा", "आत्मत्राण", "बड़े भाई साहब",
                                                       "डायरी का एक पन्ना", "तताँरा-वामीरो कथा", "तीसरी कसम के शिल्पकार शैलेंद्र",
                                                       "अब कहाँ दूसरे के दुख से दुखी होने वाले", "पतझर में टूटी पत्तियाँ", "कारतूस"]),
        ("संचयन भाग 2", "संचयन भाग 2", "jhsy1", 1, None, ["हरिहर काका", "सपनों के-से दिन", "टोपी शुक्ला"]),
    ]),
    ("Sanskrit", [
        ("शेमुषी भाग 2", "शेमुषी भाग 2", "jhsk1", 1, None, ["शुचिपर्यावरणम्", "बुद्धिर्बलवती सदा", "शिशुलालनम्", "जननी तुल्यवत्सला", "सुभाषितानि", "सौहार्दं प्रकृतेः शोभा",
                                                       "विचित्रः साक्षी", "सूक्तयः", "भूकम्पविभीषिका", "अन्योक्तयः"]),
    ]),
]}
