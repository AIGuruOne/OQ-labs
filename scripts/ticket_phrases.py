"""Generic phrase banks and writer personas for generate_tickets.py.

This file is DATA, not logic. Scenario-specific text lives in
ticket_scenarios.py; everything here can attach to any scenario.

EVERYTHING HERE IS INVENTED (BUILD_SPEC.md section 9): sites, people,
departments. People are FIRST NAMES ONLY, on purpose - a first name
identifies nobody, so no generated ticket can ever match a real
employee.

Most banks come in three registers, picked by the persona:
    "plain"  fluent English
    "nn"     non-native phrasing. These are ordinary features of
             Gulf / South Asian business English ("kindly", "the
             same", "do the needful", present continuous). They are
             written to be respectful and realistic - never comic.
    "terse"  telegraphic fragments (one-liners, agent phone notes)
"""

# ---------------------------------------------------------------------
# Invented world
# ---------------------------------------------------------------------

# site code -> weight. Three invented letters, none of them a real
# facility. The head office site dominates, like a real desk.
SITE_WEIGHTS = {"MRB": 38, "SHZ": 22, "KTF": 14, "WQR": 10, "ZFL": 8, "HBT": 5, "TMQ": 3}

FIRST_NAMES = [
    "Salim", "Khalid", "Fatma", "Aisha", "Hamed", "Said", "Maryam", "Yusuf",
    "Noor", "Badr", "Huda", "Majid", "Laila", "Nasser", "Zainab", "Tariq",
    "Rajesh", "Priya", "Anil", "Deepa", "Suresh", "Kavita", "Vinod", "Lakshmi",
    "Imran", "Sana", "Bilal", "Farah", "Jun", "Maricel", "Rowena", "Arnel",
    "Grace", "James", "Sarah", "David", "Emma", "Peter", "Helen", "Thomas",
    "Juma", "Amina", "Hassan", "Omar", "Reem", "Mona", "Karim", "Joseph",
]

DEPARTMENTS = [
    "Finance", "HR", "Procurement", "Maintenance Planning", "Operations",
    "HSE", "Projects", "Legal", "Warehouse", "Laboratory", "Engineering",
    "Contracts", "Internal Audit", "Logistics",
]

# asset prefix -> words users use for that device
DEVICE_WORDS = {
    "LAP": ["laptop", "laptop", "notebook"],
    "DSK": ["desktop", "PC", "computer"],
    "MON": ["monitor", "screen"],
    "PRN": ["printer"],
    "PHN": ["desk phone", "phone"],
    "MOB": ["mobile", "phone"],
    "TAB": ["tablet"],
}

PLANT_TAG_PREFIXES = ["P", "HX", "K", "V", "C", "E", "T", "FV"]

# ---------------------------------------------------------------------
# Writer personas. One row = one kind of ticket author.
#   voice      which problem text to use: plain | nn | note
#   register   which generic phrase register to use
#   p_*        probability of adding that optional fragment
#   backstory  (min, max) rambling filler sentences
#   typo / lower / no_apos / run_on   noise levels, 0..1
#   layout     "line" = one paragraph, "email" = greeting/body/sign-off
#   wrapper    None | "agent" (desk agent's phone note) | "forward"
#   channels   channel -> weight
# ---------------------------------------------------------------------
PERSONAS = {
    "terse": {
        "weight": 15, "voice": "note", "register": "terse",
        "p_greeting": 0.0, "p_detail": 0.05, "p_error": 0.05, "p_guess": 0.05,
        "p_tried": 0.10, "p_screenshot": 0.05, "p_ask": 0.25, "p_closing": 0.0,
        "backstory": (0, 0),
        "typo": 0.05, "lower": 0.85, "no_apos": 0.9, "run_on": 0.0,
        "layout": "line", "wrapper": None,
        "channels": {"portal": 80, "email": 20},
    },
    "casual": {
        "weight": 24, "voice": "plain", "register": "plain",
        "p_greeting": 0.35, "p_detail": 0.40, "p_error": 0.38, "p_guess": 0.30,
        "p_tried": 0.35, "p_screenshot": 0.20, "p_ask": 0.50, "p_closing": 0.25,
        "backstory": (0, 1),
        "typo": 0.04, "lower": 0.30, "no_apos": 0.5, "run_on": 0.35,
        "layout": "line", "wrapper": None,
        "channels": {"portal": 65, "email": 35},
    },
    "formal": {
        "weight": 15, "voice": "plain", "register": "plain",
        "p_greeting": 1.0, "p_detail": 0.55, "p_error": 0.45, "p_guess": 0.15,
        "p_tried": 0.35, "p_screenshot": 0.25, "p_ask": 0.70, "p_closing": 1.0,
        "backstory": (0, 1),
        "typo": 0.005, "lower": 0.0, "no_apos": 0.0, "run_on": 0.0,
        "layout": "email", "wrapper": None,
        "channels": {"email": 85, "portal": 15},
    },
    "nn_formal": {
        "weight": 15, "voice": "nn", "register": "nn",
        "p_greeting": 1.0, "p_detail": 0.35, "p_error": 0.40, "p_guess": 0.20,
        "p_tried": 0.35, "p_screenshot": 0.30, "p_ask": 0.90, "p_closing": 1.0,
        "backstory": (0, 1),
        "typo": 0.015, "lower": 0.0, "no_apos": 0.1, "run_on": 0.10,
        "layout": "email", "wrapper": None,
        "channels": {"email": 75, "portal": 25},
    },
    "nn_direct": {
        "weight": 11, "voice": "nn", "register": "nn",
        "p_greeting": 0.30, "p_detail": 0.25, "p_error": 0.32, "p_guess": 0.30,
        "p_tried": 0.35, "p_screenshot": 0.25, "p_ask": 0.60, "p_closing": 0.20,
        "backstory": (0, 0),
        "typo": 0.035, "lower": 0.35, "no_apos": 0.5, "run_on": 0.40,
        "layout": "line", "wrapper": None,
        "channels": {"portal": 70, "email": 30},
    },
    "agent_note": {
        "weight": 9, "voice": "note", "register": "terse",
        "p_greeting": 0.0, "p_detail": 0.0, "p_error": 0.15, "p_guess": 0.0,
        "p_tried": 0.0, "p_screenshot": 0.0, "p_ask": 0.0, "p_closing": 0.0,
        "backstory": (0, 0),
        "typo": 0.03, "lower": 0.55, "no_apos": 0.8, "run_on": 0.0,
        "layout": "line", "wrapper": "agent",
        "channels": {"phone": 70, "walk_in": 30},
    },
    "rambling": {
        "weight": 8, "voice": "plain", "register": "plain",
        "p_greeting": 0.50, "p_detail": 0.90, "p_error": 0.55, "p_guess": 0.70,
        "p_tried": 0.90, "p_screenshot": 0.35, "p_ask": 0.70, "p_closing": 0.40,
        "backstory": (4, 10),
        "typo": 0.03, "lower": 0.30, "no_apos": 0.6, "run_on": 0.70,
        "layout": "line", "wrapper": None,
        "channels": {"email": 60, "portal": 40},
    },
    "forwarded": {
        "weight": 4, "voice": "plain", "register": "plain",
        "p_greeting": 1.0, "p_detail": 0.80, "p_error": 0.60, "p_guess": 0.40,
        "p_tried": 0.70, "p_screenshot": 0.50, "p_ask": 0.80, "p_closing": 1.0,
        "backstory": (3, 7),
        "typo": 0.01, "lower": 0.0, "no_apos": 0.1, "run_on": 0.10,
        "layout": "email", "wrapper": "forward",
        "channels": {"email": 100},
    },
}

# ---------------------------------------------------------------------
# LABEL-BEARING fragments. If one of these is in the text, a label
# changes - so the generator always includes them when they apply.
# ---------------------------------------------------------------------

# impact. No scope sentence at all means single_user.
SCOPE_PHRASES = {
    "team": {
        "plain": [
            "The whole {dept} team has the same problem.",
            "It's not just me, all {n} of us in {dept} are affected.",
            "Same for everyone in my team, I'm just the one raising it.",
        ],
        "nn": [
            "All my colleagues in {dept} are also facing the same issue.",
            "This problem is there for full {dept} team, not only me.",
        ],
        "terse": ["whole {dept} team affected", "all of {dept} team same issue", "affects our whole team"],
    },
    "site": {
        "plain": [
            "Everyone at the {site} site is affected.",
            "It's the entire {site} office, not only our floor.",
            "I walked around and the whole {site} site has it.",
        ],
        "nn": [
            "All people in {site} site are facing the same.",
            "Complete {site} site is affected, every department.",
        ],
        "terse": ["whole {site} site affected", "entire {site} site", "all users at {site}"],
    },
    "enterprise": {
        "plain": [
            "Colleagues in {site2} and {site3} confirm the same, so it looks like every site.",
            "This seems to be company wide, I've had calls from {site2} and {site3} as well.",
        ],
        "nn": [
            "I checked with {site2} and {site3} sites also, same problem is in all sites.",
        ],
        "terse": ["all sites affected ({site}, {site2}, {site3})", "company wide - all sites"],
    },
}

# impact for REQUESTS that cover a team ("same problem" would read oddly)
SCOPE_PHRASES_REQUEST_TEAM = {
    "plain": [
        "The same is needed for {n} of us in {dept}.",
        "This is for the whole {dept} team, {n} people in total.",
    ],
    "nn": ["Same is required for all {dept} team members, total {n} persons."],
    "terse": ["for {n} ppl in {dept} team", "same for whole {dept} team ({n})"],
}

# optional: the user says out loud that it is only them (still single_user)
SCOPE_ONLY_ME = {
    "plain": ["It's only me, my colleagues are fine.", "Seems to be just my machine."],
    "nn": ["Only I am facing this, for my colleagues it is working."],
    "terse": ["only me", "just my machine"],
}

# urgency up: a concrete same-day business deadline
DEADLINE_PHRASES = {
    "plain": [
        "I have to submit the {dept} report by end of day today, so this is really blocking me.",
        "Payroll cut-off is today at 3pm and I need this sorted before then.",
        "I'm presenting to management in an hour.",
        "The auditors are on site today only and they are waiting on this.",
        "Month-end closing is today, so it can't wait until tomorrow.",
    ],
    "nn": [
        "I have to submit one report today itself, so it cannot wait.",
        "Today is the last date for month end closing, please support.",
        "Management meeting is there after one hour and I need this before.",
    ],
    "terse": ["deadline today - month end", "needed today, mgmt presentation in 1 hr", "auditors waiting, today only"],
}

# urgency down: the user says it can wait
RELAXED_PHRASES = {
    "plain": [
        "No rush on this, whenever someone has time.",
        "Not urgent at all.",
        "Low priority, I'm just logging it so it doesn't get forgotten.",
    ],
    "nn": ["It is not urgent, you can check when you are free.", "No hurry for this."],
    "terse": ["no rush", "not urgent", "low priority"],
}

# requests only: a stated future date lifts low -> medium
NEEDED_BY_PHRASES = {
    "plain": ["Needed by {date}.", "Please have it ready before {date}.", "I need it from {date} onwards."],
    "nn": ["Kindly arrange before {date}.", "It is required latest by {date}."],
    "terse": ["by {date}", "need before {date}"],
}

# ---------------------------------------------------------------------
# COLOUR fragments. These never change a label - several exist to
# tempt a model into changing one anyway.
# ---------------------------------------------------------------------

# tone without a reason. Urgency is labelled from the stated business
# effect, never from how loudly the user asks. This is the trap.
TONE_URGENT = [
    "URGENT!!!", "This is VERY urgent.", "Please treat as top priority!!",
    "urgent urgent urgent", "Kindly treat this as most urgent.", "ASAP please!!!",
]

GREETINGS = {
    "plain": ["Hi,", "Hi team,", "Hello,", "Good morning,", "Hi IT,", "Dear Service Desk,"],
    "nn": ["Dear Team,", "Dear Sir/Madam,", "Dear IT Team, Greetings.", "Greetings,", "Good day,",
           "Dear Support,", "Dear Sir,"],
    "terse": [""],
}

ASKS = {
    "plain": ["Please help.", "Can someone take a look?", "Please advise.", "Can you sort this out?",
              "Would appreciate a quick look.", "Thanks in advance."],
    "nn": ["Kindly do the needful.", "Please check and revert.", "Requesting your kind support.",
           "Kindly look into the matter.", "Please help me for this.", "Waiting for your reply."],
    "terse": ["pls fix", "pls help", "plz check", "thx"],
}

TRIED = {
    "plain": ["I already restarted twice.", "Tried restarting, no change.",
              "I cleared the cache and tried another browser.", "Signed out and back in, same thing.",
              "A colleague tried from their side as well, same result."],
    "nn": ["I did restart also but same problem is there.", "I tried two three times, no use.",
           "I checked from other computer also, same."],
    "terse": ["restarted already", "tried reboot no change"],
}

GENERIC_GUESSES = {
    "plain": ["Maybe it's because of the update last night?", "I suspect a virus.",
              "Probably the server is down.", "I think it started after the power cut."],
    "nn": ["I think it is because of some virus.", "May be server is down.",
           "I think after the update this problem started."],
    "terse": ["virus?", "server down?"],
}

# the screenshot is never attached - the corpus has no attachments
SCREENSHOTS = {
    "plain": ["Screenshot attached.", "See attached pic of the error.", "I've pasted a screenshot below.",
              "[cid:image001.png]", "(see screenshot)"],
    "nn": ["I have attached the screen shot for your reference.", "Please find the attached snap.",
           "Kindly see the attached photo."],
    "terse": ["pic attached", "see screenshot"],
}

ERROR_INTROS = {
    "plain": ["The error says:", "This is what it shows:", "Error message:", "I get this:"],
    "nn": ["It is showing error like this:", "Below message is coming:", "The error is as below:"],
    "terse": ["error:", "msg:"],
}

ASSET_MENTIONS = {
    "plain": ["Asset tag is {asset}.", "The {device} is {asset}.", "({device} {asset})", "Asset: {asset}"],
    "nn": ["My {device} asset number is {asset}.", "Asset tag of the {device} is {asset}."],
    "terse": ["{asset}", "asset {asset}", "{device} {asset}"],
}

SECOND_PROBLEM_INTROS = {
    "plain": ["Also, separate issue:", "One more thing while I have you:", "Btw, unrelated, but",
              "And another thing -"],
    "nn": ["Also one more issue is there:", "Second thing,", "Along with this one more problem:"],
    "terse": ["also", "2nd issue:", "+"],
}

# Rambling filler. None of it changes a label.
# BACKSTORY_ANY fits every ticket; BACKSTORY_PROBLEM only fits tickets
# where something is broken (it would read oddly on a plain request).
BACKSTORY_ANY = [
    "I was on leave for two weeks and only came back on Sunday.",
    "I already mentioned this to {name3} in the corridor and was told to raise a ticket.",
    "I'm not a technical person so sorry if this is the wrong place.",
    "I called the helpdesk number twice but it rang out.",
    "My manager {name3} is asking me every hour about the pending work.",
    "I normally sit in {site} but this week I'm visiting another office.",
    "I searched the intranet for a guide and found nothing useful.",
    "I have a lot of pending work because of the shutdown preparation.",
    "I asked around and nobody seems to know who owns this.",
    "I'm in meetings most of the afternoon, so mornings are better if someone needs to come to my desk.",
    "Please don't just close the ticket without calling me like last time.",
]
BACKSTORY_PROBLEM = [
    "My colleague had something similar last month and someone from IT fixed it in five minutes, but I don't remember who.",
    "It was working perfectly fine before, I haven't changed anything.",
    "This is the third time this year I'm raising the same kind of thing.",
    "We moved desks recently, not sure if that is related.",
    "Honestly it has been like this on and off for a while but today it is worse.",
    "Last time the technician said it would not happen again.",
    "I even tried from a colleague's desk to rule things out.",
    "Before this I worked at another company for many years and never saw this kind of thing.",
    "{name3} from the next office had a look and could not figure it out either.",
    "The strange thing is that on Sunday it worked for about an hour and then went back to the same behaviour.",
    "I took some notes of what I did, I can share them if it helps.",
    "Our department secretary said other floors had this in the past.",
    "I read on the internet that this can happen but the fixes there need admin rights which I don't have.",
    "To be honest I am not sure when exactly it started, maybe after the long weekend.",
]
LONG_MESSAGE_APOLOGY = "Sorry for the long message."

# earlier messages in a forwarded trail - pure noise, no labels in them
FORWARD_TRAIL = [
    "From: {author} ({dept})\nTo: {me}\n\nStill the same today. Could you chase IT for me? I don't have access to the portal from here.",
    "From: {me}\nTo: {author} ({dept})\n\nHave you tried restarting? If it is still there tomorrow send me the details and I will log it.",
    "From: {author} ({dept})\nTo: {me}\n\nFollowing up on my mail below, no change from my side. Appreciate if you can forward to the right people.",
]

CLOSINGS = {
    "plain": ["Thanks,", "Regards,", "Best regards,", "Thanks and regards,", "Cheers,", "Many thanks,"],
    "nn": ["Thanks & Regards,", "With regards,", "Thanking you,", "Best Regards,", "Regards,"],
    "terse": [""],
}

SIGNATURE_EXTRAS = [
    "{dept} | {site} | ext {ext}",
    "{dept} Department",
    "{dept}, {site} site\nExt: {ext}",
    "Sent from my mobile",
    "",
    "",
]

EMAIL_DISCLAIMER = (
    "This message and any attachments are intended for the addressee only and may be "
    "confidential. If you have received it in error please notify the sender and delete it."
)

FORWARD_TOPS = [
    "Pls see below from my team member, can you help?",
    "FYI - raising this on behalf of {author}, details in the trail below.",
    "Forwarding as {author} does not have portal access at the moment.",
    "See below. Can this be picked up please.",
]

AGENT_OPENERS = {
    "phone": ["User called.", "Call from {name} ({dept}).", "usr called -", "Phone call rcvd from {name}."],
    "walk_in": ["Walk-in user from {dept}.", "User at desk side.", "{name} from {dept} came to the desk."],
}
AGENT_CLOSERS = ["Adv user to restart - no change.", "Callback ext {ext}.", "usr not at desk after 2pm.",
                 "Remote session attempted, user had to leave.", "Logged on behalf of user.",
                 "User will send screenshot later.", ""]

GENERIC_SUBJECTS = ["help", "issue", "problem", "request", "IT support needed", "Need help", "hi",
                    "support required", "kindly help", "Issue since morning"]

# correctly-spelled word -> how people actually mistype it
COMMON_MISSPELLINGS = {
    "password": ["pasword", "passwrd", "passowrd"],
    "please": ["pls", "plz", "plese"],
    "receive": ["recieve"],
    "received": ["recieved"],
    "access": ["acess", "acces"],
    "because": ["becuase", "bcoz"],
    "screen": ["scren"],
    "working": ["workin", "wrking"],
    "problem": ["probelm", "problm"],
    "message": ["mesage", "messege"],
    "account": ["acount", "accout"],
    "monitor": ["moniter"],
    "computer": ["compter", "computr"],
    "colleague": ["collegue", "colleage"],
    "colleagues": ["collegues"],
    "attached": ["atached", "attched"],
    "tomorrow": ["tommorow"],
    "yesterday": ["yestarday"],
    "morning": ["mornng"],
    "request": ["reqest"],
    "system": ["sytem"],
    "connect": ["conect"],
    "already": ["allready"],
    "thanks": ["thx", "thnks"],
}

# neighbours on a QWERTY keyboard, for fat-finger typos
KEYBOARD_NEIGHBOURS = {
    "a": "sq", "b": "vn", "c": "xv", "d": "sf", "e": "wr", "f": "dg", "g": "fh",
    "h": "gj", "i": "uo", "k": "jl", "l": "k", "m": "n", "n": "bm", "o": "ip",
    "p": "o", "r": "et", "s": "ad", "t": "ry", "u": "yi", "v": "cb", "w": "qe",
    "y": "tu",
}
