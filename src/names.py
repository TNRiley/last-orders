#!/usr/bin/env python
"""Pub names are a small compositional language. This is its vocabulary.

A British pub name is rarely a free invention. Most are built from a handful of slots:

    [colour]  [animal]          Red Lion, White Hart, Black Horse
    [trade]   Arms              Masons Arms, Colliers Arms
    [number]  [object]          Three Horseshoes, Five Bells
    [A] and [B]                 Fox and Hounds, Rose and Crown
    [infrastructure]            Railway, Navigation, Wharf, Colliery

The lists below are hand-written, which is the honest description: they are a judgement
about what counts as a colour or a trade, not a machine-derived ontology. Anything not
matched falls through unclassified, and the page reports how large that bucket is rather
than hiding it.
"""
import re
import unicodedata

# Words that attach to a sign name without being part of it.
HOUSE_WORDS = ("inn", "hotel", "tavern", "public house", "ph", "pub", "bar",
               "alehouse", "ale house", "freehouse", "free house",
               "hostelry", "vaults", "arms hotel")

_PUNCT = re.compile(r"[^\w\s&'-]+")
_WS = re.compile(r"\s+")
_RSQUO = "’"
_LSQUO = "‘"


def fold(s):
    """Lowercase, strip accents, normalise punctuation and the definite article."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", " and ")
    s = s.replace(_RSQUO, "'").replace(_LSQUO, "'")
    s = _PUNCT.sub(" ", s.lower())
    s = _WS.sub(" ", s).strip()
    for lead in ("the ", "ye olde ", "ye old ", "ye ", "olde "):
        if s.startswith(lead):
            s = s[len(lead):]
            break
    return s.strip()


def canonical(s):
    """fold(), then drop a trailing house word and the possessive apostrophe.

    "The Miner's Arms (Inn)" -> "miners arms". Possessives go because OSM spells the
    same pub three ways: Miners Arms, Miner's Arms, Miners' Arms.
    """
    s = fold(s)
    changed = True
    while changed:
        changed = False
        for w in sorted(HOUSE_WORDS, key=len, reverse=True):
            if s.endswith(" " + w):
                s = s[: -(len(w) + 1)].strip()
                changed = True
    s = s.replace("'", "")
    return _WS.sub(" ", s).strip()


def house_word(s):
    """Which house word, if any, the original name ended with."""
    f = fold(s)
    for w in sorted(HOUSE_WORDS, key=len, reverse=True):
        if f.endswith(" " + w):
            return w
    return None


COLOURS = {
    "red", "white", "black", "blue", "green", "golden", "gold", "silver", "grey",
    "gray", "brown", "yellow", "crimson", "scarlet", "purple", "orange", "pink",
    "spotted", "dun", "bay", "roan", "pied", "tan", "chequered",
}

ANIMALS = {
    "lion", "lions", "hart", "harts", "hind", "stag", "buck", "doe", "deer",
    "horse", "horses", "mare", "colt", "pony", "nag", "bull", "bulls", "cow",
    "calf", "ox", "oxen", "ram", "lamb", "sheep", "goat", "kid", "pig", "sow",
    "hog", "boar", "swan", "swans", "eagle", "eagles", "falcon", "hawk", "kite",
    "owl", "owls", "dove", "doves", "raven", "ravens", "crow", "rook", "magpie",
    "peacock", "pheasant", "partridge", "grouse", "quail", "woodcock", "snipe",
    "plover", "lark", "swallow", "robin", "wren", "finch", "linnet", "nightingale",
    "cock", "cockerel", "hen", "chicken", "goose", "duck", "ducks", "drake",
    "dog", "dogs", "hound", "hounds", "greyhound", "greyhounds", "spaniel",
    "terrier", "retriever", "pointer", "setter", "cat", "cats", "kitten", "fox",
    "foxes", "hare", "hares", "rabbit", "badger", "otter", "stoat", "weasel",
    "ferret", "squirrel", "mole", "bear", "bears", "wolf", "wolves", "tiger",
    "leopard", "panther", "elephant", "camel", "monkey", "ape", "dolphin",
    "whale", "seal", "fish", "trout", "salmon", "pike", "perch", "carp", "eel",
    "herring", "mackerel", "crab", "lobster", "shrimp", "bee", "bees", "spider",
    "grasshopper", "dragon", "dragons", "griffin", "gryphon", "unicorn",
    "phoenix", "mermaid", "serpent", "antelope", "ibex", "bustard", "talbot",
}

NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
}

# Trades that appear before "Arms", keyed by the folded words before it.
TRADES = {
    "masons": "building", "bricklayers": "building", "carpenters": "building",
    "joiners": "building", "plasterers": "building", "slaters": "building",
    "plumbers": "building", "glaziers": "building", "builders": "building",
    "smiths": "metal", "blacksmiths": "metal", "farriers": "metal",
    "whitesmiths": "metal", "ironfounders": "metal", "founders": "metal",
    "moulders": "metal", "nailers": "metal", "cutlers": "metal",
    "locksmiths": "metal", "tinsmiths": "metal", "coppersmiths": "metal",
    "braziers": "metal",
    "wheelwrights": "craft", "coopers": "craft", "turners": "craft",
    "sawyers": "craft", "shipwrights": "craft", "boatbuilders": "craft",
    "ropers": "craft", "ropemakers": "craft", "basketmakers": "craft",
    "chairmakers": "craft", "cabinetmakers": "craft", "coachmakers": "craft",
    "weavers": "cloth", "woolcombers": "cloth", "clothiers": "cloth",
    "fullers": "cloth", "dyers": "cloth", "spinners": "cloth",
    "shearers": "cloth", "drapers": "cloth", "tailors": "cloth",
    "hatters": "cloth", "glovers": "cloth", "hosiers": "cloth",
    "silkweavers": "cloth", "flaxdressers": "cloth",
    "tanners": "leather", "curriers": "leather", "cordwainers": "leather",
    "shoemakers": "leather", "saddlers": "leather", "skinners": "leather",
    "fellmongers": "leather",
    "bakers": "food", "butchers": "food", "grocers": "food",
    "fishmongers": "food", "millers": "food", "corndealers": "food",
    "cheesemakers": "food", "saltmakers": "food",
    "brewers": "drink", "maltsters": "drink", "vintners": "drink",
    "distillers": "drink", "innkeepers": "drink",
    "farmers": "land", "ploughmans": "land", "ploughman": "land",
    "shepherds": "land", "shepherd": "land", "drovers": "land",
    "woodmans": "land", "woodman": "land", "foresters": "land",
    "gardeners": "land", "gamekeepers": "land", "hedgers": "land",
    "harvesters": "land", "reapers": "land", "haymakers": "land",
    "miners": "extraction", "colliers": "extraction", "quarrymen": "extraction",
    "quarryman": "extraction", "pitmans": "extraction", "tinners": "extraction",
    "coalminers": "extraction", "leadminers": "extraction",
    "navigation": "transport", "bargemans": "transport", "bargeman": "transport",
    "boatmans": "transport", "boatman": "transport", "watermans": "transport",
    "waterman": "transport", "fishermans": "transport", "fisherman": "transport",
    "mariners": "transport", "sailors": "transport", "seamens": "transport",
    "lightermans": "transport", "keelmans": "transport", "wherrymans": "transport",
    "carriers": "transport", "carters": "transport", "waggoners": "transport",
    "wagoners": "transport", "hauliers": "transport", "platelayers": "transport",
    "railwaymans": "transport", "railwayman": "transport",
    "enginemans": "transport", "engineers": "transport", "mechanics": "transport",
    "firemans": "transport", "pilots": "transport", "airmans": "transport",
    "potters": "other", "glassmakers": "other", "glassblowers": "other",
    "papermakers": "other", "printers": "other", "bookbinders": "other",
    "chandlers": "other", "soapmakers": "other", "brickmakers": "other",
    "limeburners": "other", "watchmakers": "other", "clockmakers": "other",
    "jewellers": "other", "goldsmiths": "other", "barbers": "other",
    "sextons": "other", "ringers": "other", "bellringers": "other",
    "cricketers": "sport", "bowlers": "sport", "huntsmans": "sport",
    "huntsman": "sport", "anglers": "sport", "archers": "sport",
    "footballers": "sport", "jockeys": "sport",
    "volunteers": "military", "riflemans": "military", "rifleman": "military",
    "grenadiers": "military", "fusiliers": "military", "artillery": "military",
    "yeomans": "military", "soldiers": "military", "troopers": "military",
    "dragoons": "military", "marines": "military", "legion": "military",
}

# Names that remember transport or industry. Each group is tested against a
# different kind of line on the ground, so the groups are kept apart.
# "mallard" was here for the A4 locomotive and came out on finishing the build: nearly every
# pub called The Mallard is named for the duck. "grand junction" moved to the canal words
# (the Grand Junction Canal); it was matching as a railway junction.
RAIL_WORDS = {
    "railway", "railways", "rail", "station", "stationmasters", "junction",
    "locomotive", "signal", "signalbox", "sidings", "siding", "platform",
    "terminus", "puffing billy", "flying scotsman", "pullman",
    "great western", "great northern", "great eastern", "great central",
    "midland", "caledonian", "brunel", "stephensons", "railwaymans",
    "railwayman", "platelayers", "enginemans", "engineman", "whistle stop",
    "level crossing", "goods yard", "iron horse", "steam engine", "engine shed",
}
CANAL_WORDS = {
    "navigation", "canal", "wharf", "lock", "locks", "lock keeper",
    "lockkeepers", "barge", "barges", "boat", "boatmans", "boatman",
    "narrowboat", "towpath", "basin", "aqueduct", "bridgewater",
    "lightermans", "lighterman", "keelmans", "wherrymans", "packet",
    "grand union", "grand junction", "flyboat",
}
EXTRACTION_WORDS = {
    "miners", "colliers", "colliery", "pit", "pithead", "pitman", "pitmans",
    "coal", "quarry", "quarrymen", "quarryman", "tinners", "winding wheel",
    "davy lamp", "safety lamp", "coke oven", "ironworks", "furnace", "foundry",
    "forge", "limekiln", "lime kiln", "mineshaft", "headstocks",
}

_AND = re.compile(r"^(.*?)\s+and\s+(.*)$")


def parse(name):
    """Describe a pub name in terms of the vocabulary above.

    Every field is optional except `canon`; a name that matches nothing comes back with
    no slots filled, which is a real and reportable outcome.
    """
    canon = canonical(name)
    words = canon.split()
    out = {"canon": canon, "words": len(words)}

    if words:
        if words[0] in COLOURS:
            out["colour"] = words[0]
            if len(words) >= 2 and words[1] in ANIMALS:
                out["animal"] = words[1]
                out["template"] = "colour+animal"
        if words[0] in NUMBERS:
            out["number"] = NUMBERS[words[0]]
            out.setdefault("template", "number+object")
            if len(words) >= 2:
                out["counted"] = " ".join(words[1:])
        if words[-1] == "arms" and len(words) >= 2:
            trade_key = " ".join(words[:-1])
            out["arms"] = trade_key
            if trade_key in TRADES:
                out["trade"] = trade_key
                out["trade_group"] = TRADES[trade_key]
            out.setdefault("template", "x+arms")

    m = _AND.match(canon)
    if m:
        out["pair"] = [m.group(1).strip(), m.group(2).strip()]
        out.setdefault("template", "a+and+b")

    if "animal" not in out:
        for w in words:
            if w in ANIMALS:
                out["animal"] = w
                break

    def hit(vocab):
        if canon in vocab:
            return True
        if any(w in vocab for w in words):
            return True
        return any(p in canon for p in vocab if " " in p)

    if hit(CANAL_WORDS) and "grand junction" in canon:
        out["remembers"] = "canal"
    elif hit(RAIL_WORDS):
        out["remembers"] = "rail"
    elif hit(CANAL_WORDS):
        out["remembers"] = "canal"
    elif hit(EXTRACTION_WORDS):
        out["remembers"] = "extraction"

    return out


if __name__ == "__main__":
    import sys
    samples = sys.argv[1:] or [
        "The Red Lion", "Ye Olde Miner's Arms (Inn)", "Three Horseshoes",
        "Fox & Hounds", "The Railway Tavern", "Navigation Inn",
        "The Colliers Arms", "White Hart Hotel", "Rose and Crown",
    ]
    for n in samples:
        print("%-30s %s" % (n, parse(n)))
