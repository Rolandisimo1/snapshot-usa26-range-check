"""Resolve mammal names to Mammal Diversity Database (MDD) species IDs.

Rules (mdd-taxonomy lab skill):
  * accepted exact match on sciName -> accepted_exact
  * else full-binomial match on the synonym table's original combination -> synonym
    (one linked species) or ambiguous_split (several)
  * never a bare-epithet match across genera; anything else -> unresolved
Comparisons downstream use the integer MDD id, never the name string.
"""
import os, re
import pandas as pd

MDD_VERSION = "MDD v2.5"
MDD_DOI = "10.5281/zenodo.21654811"
HERE = os.path.dirname(os.path.abspath(__file__))
MDD_DIR = os.path.join(HERE, "..", "data_raw", "mdd")


def load_mdd(mdd_dir=MDD_DIR):
    sp = pd.read_csv(os.path.join(mdd_dir, "MDD_v2.5_6904species.csv"), dtype=str)
    syn = pd.read_csv(os.path.join(mdd_dir, "Species_Syn_v2.5.csv"), dtype=str, low_memory=False)
    for col in ["sciName", "id", "genus", "countryDistribution", "mainCommonName", "family"]:
        if col not in sp.columns:
            raise KeyError(f"MDD species table missing column {col}")
    for col in ["MDD_species", "MDD_original_combination", "MDD_nomenclature_status"]:
        if col not in syn.columns:
            raise KeyError(f"MDD synonym table missing column {col}")
    sp["sci"] = sp.sciName.str.replace("_", " ")
    syn["oc"] = syn.MDD_original_combination.fillna("").str.replace("_", " ").str.strip()
    syn["acc"] = syn.MDD_species.fillna("").str.replace("_", " ")
    return sp, syn


def normalize(name):
    """Return (binomial, note). Strips 'U. arctos' style repeats and trinomials."""
    if name is None or (isinstance(name, float)):
        return None, "missing"
    s = re.sub(r"\s+", " ", str(name)).strip()
    if " or " in s:
        return s, "two_species_choice"
    parts = s.split(" ")
    # 'Ursus U. arctos' -> 'Ursus arctos'
    parts = [p for p in parts if not re.fullmatch(r"[A-Z]\.", p)]
    if len(parts) >= 3:
        return " ".join(parts[:2]), "trinomial_reduced:" + s
    return " ".join(parts), ""


class Resolver:
    def __init__(self, mdd_dir=MDD_DIR):
        self.sp, self.syn = load_mdd(mdd_dir)
        self.acc = self.sp.set_index("sci")
        self.by_id = self.sp.set_index("id")
        self._cache = {}

    def resolve(self, name):
        if name in self._cache:
            return self._cache[name]
        b, note = normalize(name)
        out = dict(verbatim=name, normalized=b, norm_note=note, mdd_id=None,
                   mdd_sciName=None, match_type="unresolved", syn_status=None, candidates=None)
        if b is None:
            out["match_type"] = "missing"
        elif note == "two_species_choice":
            out["match_type"] = "two_species_choice"
        elif b in self.acc.index:
            r = self.acc.loc[b]
            out.update(mdd_id=r["id"], mdd_sciName=b, match_type="accepted_exact")
        else:
            h = self.syn[self.syn.oc == b]
            ids = h.acc.unique()
            if len(ids) == 1 and ids[0] in self.acc.index:
                out.update(mdd_id=self.acc.loc[ids[0], "id"], mdd_sciName=ids[0], match_type="synonym",
                           syn_status=";".join(sorted(h.MDD_nomenclature_status.dropna().unique())))
            elif len(ids) > 1:
                out.update(match_type="ambiguous_split", candidates=";".join(ids))
        self._cache[name] = out
        return out

    def table(self, names):
        return pd.DataFrame([self.resolve(n) for n in names])

    def genus_in_us(self, genus):
        g = self.sp[self.sp.genus == genus]
        if g.empty:
            return None
        return bool(g.countryDistribution.fillna("").str.contains("United States").any())

    def species_in_us(self, mdd_id):
        return "United States" in str(self.by_id.loc[mdd_id, "countryDistribution"])

    def common(self, mdd_id):
        return self.by_id.loc[mdd_id, "mainCommonName"]
