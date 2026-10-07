"""Verified source records (quotes read in primary texts; see docs/trial_rules.md)."""

from voxeltrace.rules.schema import RuleSource

PERCIST_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC2755245/"
PPERCIST_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC4976461/"
QIBA_URL = "https://qibawiki.rsna.org/images/c/c7/QIBA_FDG-PET_Profile_v114.pdf"
EANM_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC4315529/"

PERCIST_UPTAKE = RuleSource(
    citation="Wahl RL et al. PERCIST 1.0. J Nucl Med 2009;50 Suppl 1:122S-150S",
    url=PERCIST_URL,
    locator="Table (PERCIST 1.0 key points)",
    quote="Uptake time of baseline study and follow-up study must be within 15 min of each "
    "other to be assessable. Typically, these are at mean of 60 min after injection but "
    "no less than 50 min after injection.",
    verification="PRIMARY_TEXT",
)
PPERCIST_UPTAKE = RuleSource(
    citation="O JH, Lodge MA, Wahl RL. Practical PERCIST. Radiology 2016;280:576-584",
    url=PPERCIST_URL,
    locator="Practical PERCIST, comparability",
    quote="The injection-to-imaging start time for both baseline and follow-up imaging should "
    "be greater than or equal to 50 minutes and less than or equal to 70 minutes.",
    verification="PRIMARY_TEXT_VIA_FETCH",
)
PERCIST_LIVER = RuleSource(
    citation="Wahl RL et al. PERCIST 1.0 (Table); O JH et al. Practical PERCIST 2016",
    url=PPERCIST_URL,
    locator="PERCIST Table; Practical PERCIST liver criterion",
    quote="To be assessable, differences between baseline and follow-up SUL in the liver must "
    "be (a) less than or equal to 20% of the larger of the two liver measurements and "
    "(b) less than or equal to 0.3 SUL units.",
    verification="PRIMARY_TEXT_VIA_FETCH",
)
PERCIST_DOSE = RuleSource(
    citation="O JH et al. Practical PERCIST 2016; Wahl RL et al. PERCIST 1.0",
    url=PPERCIST_URL,
    locator="comparability",
    quote="difference between the injected dose of FDG (in "
    "megabecquerels) ... should be less than or equal to 20%.",
    verification="PRIMARY_TEXT_VIA_FETCH",
)
PERCIST_EQUIP = RuleSource(
    citation="Wahl RL et al. PERCIST 1.0",
    url=PERCIST_URL,
    locator="Table, equipment",
    quote="Same scanner, or same scanner model at same site, injected dose, acquisition "
    "protocol (2- vs. 3-dimensional), and software for reconstruction, should be used.",
    verification="PRIMARY_TEXT",
)
PERCIST_MEASURABLE = RuleSource(
    citation="Wahl RL et al. PERCIST 1.0",
    url=PERCIST_URL,
    locator="main text; Figure 3",
    quote="Each baseline (pretreatment) tumor SUL peak must be 1.5 x mean liver SUL + 2 SDs "
    "of mean SUL.",
    verification="PRIMARY_TEXT",
)
QIBA_TIMING = RuleSource(
    citation="QIBA FDG-PET/CT Profile v1.14 (2016, updated 2023)",
    url=QIBA_URL,
    locator="3.2.1.1 Timing of Image Data Acquisition",
    quote="While the 'target' tracer uptake time is 60 minutes, the 'acceptable' window is "
    "from 55 to 75 minutes ... it is essential to apply the same time interval with target "
    "window of +/- 10 minutes provided that the scan must not begin prior to 55 minutes "
    "after the injection of FDG.",
    verification="PRIMARY_TEXT",
)
QIBA_SYSTEM = RuleSource(
    citation="QIBA FDG-PET/CT Profile v1.14",
    url=QIBA_URL,
    locator="longitudinal studies",
    quote="it is strongly recommended that subjects in a longitudinal study be scanned on the "
    "same PET/CT system with the same software version whenever possible.",
    verification="PRIMARY_TEXT",
)
EANM_TIMING = RuleSource(
    citation="Boellaard R et al. EANM FDG PET/CT guideline v2.0. EJNMMI 2015;42:328-354",
    url=EANM_URL,
    locator="Procedure for preparation and administration of FDG",
    quote="a 60 min interval is recommended with an acceptable range of 55 - 75 min ... it is "
    "essential to apply the same uptake interval to within 10 min. In addition, the use of "
    "the same PET/CT system and identical acquisition and reconstruction settings should "
    "be applied when making multiple examinations in the same patient.",
    verification="PRIMARY_TEXT",
)
EANM_EARL = RuleSource(
    citation="Boellaard R et al. EANM FDG PET/CT guideline v2.0",
    url=EANM_URL,
    locator="PET image reconstruction",
    quote="For quantitative assessment of the FDG PET/CT study, the EARL-approved "
    "reconstruction settings, which meet the standardised performance standards, should "
    "be used.",
    verification="PRIMARY_TEXT",
)
VT = RuleSource(
    citation="VoxelTrace engineering criteria (not a published standard)",
    url=None,
    locator="docs/comparability.md, docs/quantification.md",
    quote="strict SUVbw path; reconstruction/correction/voxel identity checks",
    verification="PRIMARY_TEXT",
)
