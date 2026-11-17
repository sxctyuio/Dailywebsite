#!/usr/bin/env python3
"""
The Daily Spin — nightly story builder (runs in GitHub Actions).

Picks 3 random topics + AI for tomorrow, asks Claude (with live web search) to find a real,
lesser-known news/feature article for each, plus a backup, and writes:
  data/stories.json      - the day the page shows
  data/archive/DATE.json - a copy for history
  data/seen.json         - hash map of every article URL already used, so nothing repeats

Needs the ANTHROPIC_API_KEY environment variable (set from a GitHub Actions secret).
Standard library only — no pip install needed.
"""
import datetime, hashlib, json, os, random, re, sys, time, urllib.error, urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

MODEL = "claude-sonnet-5-5"
TZ = ZoneInfo("America/Los_Angeles")
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

T = lambda name, desc, color, seeds: {"name": name, "desc": desc, "color": color, "seeds": seeds}
TOPICS = {
    "physics": T("Physics", "Matter, energy, motion and force", "#f59e0b", ["granular materials and sandpiles", "strange acoustics", "friction", "fluid dynamics in nature", "experiments near absolute zero", "the physics of everyday objects", "forgotten physics experiments", "measurement and units"]),
    "chemistry": T("Chemistry", "Composition, structure and reactions of matter", "#fb923c", ["pigments and dyes", "element discoveries", "accidental discoveries", "flavor and smell chemistry", "glass", "chemistry of food", "historic poisons", "catalysts"]),
    "biology": T("Biology", "Living organisms and life processes", "#22c55e", ["bizarre life cycles", "regeneration", "extremophiles", "symbiosis", "bioluminescence", "parasites that control hosts", "biological clocks", "sleep in animals"]),
    "astronomy": T("Astronomy", "Celestial objects, space and the universe", "#818cf8", ["meteorites that landed somewhere odd", "amateur astronomers' discoveries", "comets", "light pollution", "moons of the outer planets", "eclipses in history", "old star catalogs", "asteroids"]),
    "geology": T("Geology", "Earth's structure, composition and history", "#a3a3a3", ["sinkholes", "minerals with strange histories", "ancient supercontinents", "volcanic islands", "caves", "rocks that move", "deep time", "salt deposits"]),
    "meteorology": T("Meteorology", "The atmosphere, weather and forecasting", "#60a5fa", ["history of forecasting", "weird weather events", "lightning", "clouds and cloud names", "fog", "famous storms", "giant hail", "weather folklore that's true"]),
    "oceanography": T("Oceanography", "Oceans and marine ecosystems", "#06b6d4", ["deep-sea creatures", "ocean currents and flotsam", "rogue waves", "shipwreck ecosystems", "mapping the sea floor", "coral", "sea ice", "tides"]),
    "ecology": T("Ecology", "Organisms and their environment", "#34d399", ["rewilding", "invasive species", "keystone species", "urban wildlife", "island ecosystems", "fire ecology", "pollinators", "food webs"]),
    "botany": T("Botany", "Plants", "#84cc16", ["carnivorous plants", "ancient trees", "seed vaults", "plant communication", "rare flowers", "plant hunters", "fungal networks", "crops with surprising histories"]),
    "zoology": T("Zoology", "Animals and animal behavior", "#eab308", ["animal navigation", "animal intelligence", "migrations", "camouflage", "animals that use tools", "rediscovered species", "animal communication", "strange mating rituals"]),
    "microbiology": T("Microbiology", "Bacteria, viruses and microscopic life", "#14b8a6", ["microbes in odd places", "fermentation", "bacteriophages", "the microbiome", "microbes in history", "antibiotics from soil", "mold and fungi", "microbial mats"]),
    "genetics": T("Genetics", "Genes, heredity and variation", "#c084fc", ["ancient DNA", "rare inherited traits", "genetic mysteries in populations", "domestication genes", "twins research", "jumping genes", "DNA in forensics history", "gene editing"]),
    "biochemistry": T("Biochemistry", "Chemical processes inside living things", "#e879f9", ["venoms", "enzymes in industry", "drugs discovered in nature", "spider silk", "antifreeze proteins", "photosynthesis tricks", "metabolism oddities", "hormones"]),
    "astrophysics": T("Astrophysics", "The physics of the universe", "#6366f1", ["neutron stars", "cosmic rays", "dark matter hunts", "gravitational waves", "supernovae in history", "black holes", "the cosmic microwave background", "exoplanet weirdness"]),
    "seismology": T("Seismology", "Earthquakes and seismic waves", "#ef4444", ["historic earthquakes", "slow earthquakes", "tsunamis", "quakes on other planets", "earthquake prediction myths", "animals and quakes", "induced earthquakes", "building against quakes"]),
    "cs": T("Computer Science", "Computation, information and systems", "#38bdf8", ["early computers", "famous bugs", "internet history", "cryptography", "algorithms in everyday life", "video game history", "origins of programming languages", "data storage oddities"]),
    "math": T("Mathematics", "Numbers, shapes and logical patterns", "#facc15", ["unsolved problems", "mathematicians with unusual lives", "math in art", "probability puzzles", "prime numbers", "topology and maps", "ancient math", "codes and ciphers"]),
    "envsci": T("Environmental Science", "Physical, chemical and biological interactions", "#4ade80", ["pollution mysteries", "river restoration", "microplastics", "drought and water", "air quality history", "soil", "glaciers", "urban heat"]),
    "anatomy": T("Anatomy", "The structures of living bodies", "#f87171", ["odd body parts", "history of anatomy", "the senses", "vestigial structures", "animal anatomy oddities", "the skeleton", "brain structure", "muscles and movement"]),
    "psychology": T("Psychology", "Mind and behavior", "#f472b6", ["famous experiments revisited", "memory", "perception and illusions", "habits", "decision making", "language and thought", "crowd behavior", "sleep and dreams"]),
    "politics": T("Politics & Civics", "How governments and laws work", "#94a3b8", ["origins of political institutions", "odd laws and their history", "voting systems", "constitutions", "diplomacy history", "micronations", "elections around the world", "how laws get made in different countries"]),
    "archaeology": T("Archaeology", "Uncovering the human past", "#d97706", ["lost cities", "shipwrecks", "ancient technology", "deciphered scripts", "everyday life in the ancient world", "archaeological frauds", "underwater archaeology", "ancient food"]),
    "medicine": T("Medicine", "Health, disease and treatment", "#f43f5e", ["medical history oddities", "forgotten pioneers", "vaccine history", "surgery before anesthesia", "rare diseases", "epidemics in history", "medical devices", "placebos"]),
    "gk": T("General Knowledge", "A bit of everything", "#f5a524", ["inventions with odd origins", "word origins", "maps and borders", "history of everyday objects", "sports history", "food history", "calendars and time", "festivals"]),
    "linguistics": T("Linguistics", "Language and how it works", "#a78bfa", ["endangered languages", "invented languages", "writing systems", "whistled languages", "slang history", "sign languages", "translation puzzles", "dialects"]),
    "engineering": T("Engineering", "How things are designed and built", "#fb7185", ["bridges and failures", "canals and tunnels", "clocks and mechanisms", "infrastructure nobody notices", "early flight", "dams", "materials", "megaprojects"]),
    "economics": T("Economics", "Money, markets and trade", "#10b981", ["strange currencies", "trade routes", "bubbles and crashes", "commodities with odd histories", "economic experiments", "inflation stories", "markets for unusual things", "history of banking"]),
    "paleontology": T("Paleontology", "Life in deep time", "#b45309", ["fossils found by amateurs", "extinct giants", "trace fossils", "amber", "mass extinctions", "dinosaur misconceptions", "fossil rivalries", "ice age animals"]),
}
AI = T("Artificial Intelligence", "Machines that learn and reason", "#a78bfa", ["AI history", "AI in science", "AI and art", "robots", "AI mistakes and failures", "AI and games", "AI ethics debates", "machine translation", "self-driving vehicles", "AI in medicine", "chatbot history", "neural network history"])
TWISTS = ["any era", "the 1800s", "before 1500", "the 20th century", "the last few years", "Asia", "Africa", "South America", "Oceania", "Europe", "the Arctic", "a small town", "one person's obsession", "an accident", "a failure"]


def norm_url(u):
    return re.sub(r"[#?].*$", "", str(u or "")).rstrip("/").lower()


def url_key(u):
    return hashlib.sha1(norm_url(u).encode()).hexdigest()[:16]


def load(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def call_claude(messages):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": MODEL, "max_tokens": 6000, "messages": messages,
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
        }).encode(),
        headers={"content-type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                 "anthropic-version": "2023-06-01"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code in (429, 500, 529) and attempt < 2:
                time.sleep(20 * (attempt + 1)); continue
            sys.exit(f"Claude API error {e.code}: {body}")


def prompt_for(topic, seen_urls):
    seen = "\n".join(seen_urls[-150:]) or "(none)"
    politics = "\n- Keep it neutral: civics, history or how systems work, not partisan opinion." if topic["name"].startswith("Politics") else ""
    return f"""You are picking articles for a curious reader's daily learning page.

Topic: {topic['name']} ({topic['desc']}). Search angle: "{random.choice(topic['seeds'])}". Optional twist if it fits naturally: {random.choice(TWISTS)}.

Find TWO different articles (a main one and a backup):
- Use web_search for niche, specific, lesser-known stories on this angle (not the famous classic of the field). Refine and search again as needed.
- For each, take the FIRST search result that is a journalism, magazine or news feature article (e.g. Smithsonian, Atlas Obscura, BBC, NPR, The Atlantic, Quanta, Knowable, Hakai, Nautilus, Aeon, Wired, The Guardian, Scientific American, National Geographic, Ars Technica, IEEE Spectrum, The Conversation, Science News, AP, Reuters).
- Skip Wikipedia, encyclopedias, scientific papers/journals/preprints, press-release sites, and these already-used URLs:
{seen}
- For each article, pick 3-4 "related" links from the OTHER search results: at least 1 Wikipedia article and at least 1 science/reference source (NASA, NOAA, a university, a museum, a journal's news section, a science explainer).{politics}
- Write summaries, facts and questions in your own words, based only on what the search results say. Never copy sentences.

Finish with ONLY this JSON (nothing after it):
{{"main": ARTICLE, "alt": ARTICLE}}
where ARTICLE = {{"title":"headline as published","outlet":"publication","url":"exact URL from the search results","year":2024,
"summary":"3-4 plain-language sentences","facts":["4 short surprising facts"],"questions":["3 open-ended discussion questions"],
"related":[{{"t":"title","u":"exact URL from the search results","k":"wiki or sci"}}]}}"""


def find_articles(topic, seen_urls):
    messages = [{"role": "user", "content": prompt_for(topic, seen_urls)}]
    content = []
    for _ in range(5):
        resp = call_claude(messages)
        content += resp.get("content", [])
        if resp.get("stop_reason") != "pause_turn":
            break
        messages += [{"role": "assistant", "content": resp["content"]}]
    found = {norm_url(r["url"]) for b in content if b.get("type") == "web_search_tool_result" and isinstance(b.get("content"), list)
             for r in b["content"] if r.get("url")}
    text = "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
    start, end = text.rfind('{"main"'), text.rfind("}")
    if start < 0:
        start = text.find("{")
    try:
        data = json.loads(text[start:end + 1])
    except Exception:
        return None, None
    used = {norm_url(u) for u in seen_urls}

    def clean(a):
        if not isinstance(a, dict) or not a.get("title") or not a.get("url") or not a.get("summary"):
            return None
        if norm_url(a["url"]) not in found or norm_url(a["url"]) in used:   # link must come from a real search result
            return None
        strs = lambda x, n: [s for s in (x or []) if isinstance(s, str) and s.strip()][:n]
        related = [{"t": str(r["t"]), "u": str(r["u"]), "k": "wiki" if "wikipedia.org" in str(r["u"]) else "sci"}
                   for r in (a.get("related") or []) if isinstance(r, dict) and r.get("t") and norm_url(r.get("u")) in found][:4]
        return {"title": str(a["title"]), "outlet": str(a.get("outlet", "")), "url": str(a["url"]), "year": a.get("year"),
                "summary": str(a["summary"]), "facts": strs(a.get("facts"), 5), "questions": strs(a.get("questions"), 4), "related": related}

    main, alt = clean(data.get("main")), clean(data.get("alt"))
    if alt and main and norm_url(alt["url"]) == norm_url(main["url"]):
        alt = None
    return main or alt, (alt if main else None)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else (datetime.datetime.now(TZ).date() + datetime.timedelta(days=1)).isoformat()
    (DATA / "archive").mkdir(parents=True, exist_ok=True)
    if (DATA / "archive" / f"{target}.json").exists():
        print(f"{target} already done"); return
    seen = load(DATA / "seen.json", {})
    yesterday = (datetime.date.fromisoformat(target) - datetime.timedelta(days=1)).isoformat()
    prev_ids = {t["id"] for t in load(DATA / "archive" / f"{yesterday}.json", {}).get("topics", [])}
    ids = random.sample([k for k in TOPICS if k not in prev_ids], 3) + ["ai"]

    topics_out = []
    for tid in ids:
        topic = AI if tid == "ai" else TOPICS[tid]
        seen_urls = [v["u"] for v in seen.values()]
        main_a, alt_a = None, None
        for _ in range(2):                       # one retry if nothing valid came back
            main_a, alt_a = find_articles(topic, seen_urls)
            if main_a:
                break
        if not main_a:
            print(f"!! no article for {tid}, skipping"); continue
        for a in (main_a, alt_a):
            if a:
                seen[url_key(a["url"])] = {"t": a["title"], "u": a["url"], "c": tid, "d": target}
        topics_out.append({"id": tid, "name": topic["name"], "desc": topic["desc"], "color": topic["color"],
                           "article": main_a, "alt": alt_a})
        print(f"{tid}: {main_a['title']} ({main_a['outlet']})")

    if not topics_out:
        sys.exit("No stories found.")
    day = {"date": target, "topics": topics_out}
    (DATA / "stories.json").write_text(json.dumps(day, indent=1))
    (DATA / "archive" / f"{target}.json").write_text(json.dumps(day, indent=1))
    (DATA / "seen.json").write_text(json.dumps(seen, indent=1))


if __name__ == "__main__":
    main()
