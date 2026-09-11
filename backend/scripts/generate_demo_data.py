"""
Demo/synthetic data generators used by scripts/seed_database.py.

Drug, gene, and disease *names* are real, publicly-known terms (there is no
usable "fake biology" - a made-up gene symbol wouldn't demo anything). What is
synthetic here are the *relationships* between them (which gene is "associated"
with which disease, which target a given drug hits, interaction confidence
scores) - none of this is sourced from a curated biomedical database, and every
row is tagged with app.core.constants.DEMO_DATA_DISCLAIMER. The repurposing
predictions generated from this data are computed for real by the same AI
pipeline used in production (app/ai/pipeline.py) - only the *inputs* are
synthetic, the scoring is not faked.
"""
import random
import uuid
from datetime import datetime, timedelta, timezone

from faker import Faker
from sqlalchemy.orm import Session

from app.core.constants import (
    DEMO_DATA_DISCLAIMER,
    DatasetStatus,
    ExperimentStatus,
    ExperimentType,
    NotificationType,
    ProjectStatus,
    RoleName,
)
from app.core.security import hash_password
from app.models.compound import Compound
from app.models.dataset import Dataset
from app.models.disease import Disease
from app.models.drug import Drug
from app.models.experiment import Experiment
from app.models.gene import Gene
from app.models.interaction import Interaction
from app.models.project import Project
from app.models.target import Target
from app.models.user import User
from app.services.auth_service import get_or_create_role

fake = Faker()
random.seed(7)
Faker.seed(7)

DEMO_META = {"data_source": "demo", "disclaimer": DEMO_DATA_DISCLAIMER}

DRUG_CATALOG = [
    ("Metformin", "Metformin hydrochloride", "Biguanide", "Decreases hepatic glucose production and increases insulin sensitivity."),
    ("Atorvastatin", "Atorvastatin calcium", "Statin", "Inhibits HMG-CoA reductase, reducing cholesterol synthesis."),
    ("Losartan", "Losartan potassium", "Angiotensin II receptor blocker", "Blocks the angiotensin II type-1 receptor."),
    ("Metoprolol", "Metoprolol tartrate", "Beta blocker", "Selectively blocks beta-1 adrenergic receptors."),
    ("Aspirin", "Acetylsalicylic acid", "NSAID", "Inhibits cyclooxygenase (COX-1/COX-2), reducing prostaglandin synthesis."),
    ("Ibuprofen", "Ibuprofen", "NSAID", "Non-selective COX inhibitor with analgesic and anti-inflammatory effects."),
    ("Omeprazole", "Omeprazole", "Proton pump inhibitor", "Irreversibly inhibits the H+/K+ ATPase in gastric parietal cells."),
    ("Sertraline", "Sertraline hydrochloride", "SSRI", "Selectively inhibits serotonin reuptake."),
    ("Fluoxetine", "Fluoxetine hydrochloride", "SSRI", "Selectively inhibits serotonin reuptake."),
    ("Amlodipine", "Amlodipine besylate", "Calcium channel blocker", "Inhibits calcium ion influx into vascular smooth muscle."),
    ("Simvastatin", "Simvastatin", "Statin", "Inhibits HMG-CoA reductase."),
    ("Levothyroxine", "Levothyroxine sodium", "Thyroid hormone", "Synthetic T4 hormone replacement."),
    ("Warfarin", "Warfarin sodium", "Anticoagulant", "Inhibits vitamin K epoxide reductase."),
    ("Clopidogrel", "Clopidogrel bisulfate", "Antiplatelet", "Irreversibly inhibits the P2Y12 receptor."),
    ("Gabapentin", "Gabapentin", "Anticonvulsant", "Modulates voltage-gated calcium channels (alpha2-delta subunit)."),
    ("Hydrochlorothiazide", "Hydrochlorothiazide", "Thiazide diuretic", "Inhibits sodium reabsorption in the distal tubule."),
    ("Pantoprazole", "Pantoprazole sodium", "Proton pump inhibitor", "Irreversibly inhibits gastric H+/K+ ATPase."),
    ("Furosemide", "Furosemide", "Loop diuretic", "Inhibits the Na-K-Cl cotransporter in the loop of Henle."),
    ("Prednisone", "Prednisone", "Corticosteroid", "Binds glucocorticoid receptors, broadly suppressing inflammation."),
    ("Insulin glargine", "Insulin glargine", "Insulin analog", "Long-acting basal insulin receptor agonist."),
    ("Metronidazole", "Metronidazole", "Antibiotic/antiprotozoal", "Disrupts DNA synthesis in anaerobic organisms."),
    ("Azithromycin", "Azithromycin", "Macrolide antibiotic", "Inhibits bacterial protein synthesis at the 50S ribosomal subunit."),
    ("Amoxicillin", "Amoxicillin", "Penicillin antibiotic", "Inhibits bacterial cell wall synthesis."),
    ("Doxycycline", "Doxycycline hyclate", "Tetracycline antibiotic", "Inhibits bacterial protein synthesis at the 30S ribosomal subunit."),
    ("Ciprofloxacin", "Ciprofloxacin", "Fluoroquinolone antibiotic", "Inhibits bacterial DNA gyrase and topoisomerase IV."),
    ("Rosuvastatin", "Rosuvastatin calcium", "Statin", "Inhibits HMG-CoA reductase."),
    ("Pravastatin", "Pravastatin sodium", "Statin", "Inhibits HMG-CoA reductase."),
    ("Lisinopril", "Lisinopril", "ACE inhibitor", "Inhibits angiotensin-converting enzyme."),
    ("Enalapril", "Enalapril maleate", "ACE inhibitor", "Inhibits angiotensin-converting enzyme."),
    ("Ramipril", "Ramipril", "ACE inhibitor", "Inhibits angiotensin-converting enzyme."),
    ("Valsartan", "Valsartan", "Angiotensin II receptor blocker", "Blocks the angiotensin II type-1 receptor."),
    ("Carvedilol", "Carvedilol", "Beta blocker", "Non-selective beta and alpha-1 receptor blocker."),
    ("Diltiazem", "Diltiazem hydrochloride", "Calcium channel blocker", "Inhibits calcium influx in cardiac and smooth muscle."),
    ("Verapamil", "Verapamil hydrochloride", "Calcium channel blocker", "Inhibits calcium influx in cardiac and smooth muscle."),
    ("Spironolactone", "Spironolactone", "Aldosterone antagonist", "Competitively blocks the mineralocorticoid receptor."),
    ("Allopurinol", "Allopurinol", "Xanthine oxidase inhibitor", "Inhibits xanthine oxidase, reducing uric acid production."),
    ("Methotrexate", "Methotrexate", "Antimetabolite/DMARD", "Inhibits dihydrofolate reductase."),
    ("Hydroxychloroquine", "Hydroxychloroquine sulfate", "Antimalarial/DMARD", "Interferes with lysosomal activity and antigen presentation."),
    ("Sulfasalazine", "Sulfasalazine", "DMARD", "Anti-inflammatory action mediated by its metabolites."),
    ("Leflunomide", "Leflunomide", "DMARD", "Inhibits dihydroorotate dehydrogenase, suppressing lymphocyte proliferation."),
    ("Tacrolimus", "Tacrolimus", "Calcineurin inhibitor", "Inhibits calcineurin, suppressing T-cell activation."),
    ("Cyclosporine", "Cyclosporine", "Calcineurin inhibitor", "Inhibits calcineurin, suppressing T-cell activation."),
    ("Rituximab", "Rituximab", "Monoclonal antibody", "Targets CD20 on B lymphocytes."),
    ("Infliximab", "Infliximab", "Monoclonal antibody", "Neutralizes tumor necrosis factor-alpha (TNF-alpha)."),
    ("Adalimumab", "Adalimumab", "Monoclonal antibody", "Neutralizes tumor necrosis factor-alpha (TNF-alpha)."),
    ("Etanercept", "Etanercept", "TNF inhibitor (fusion protein)", "Acts as a soluble TNF-alpha receptor decoy."),
    ("Imatinib", "Imatinib mesylate", "Tyrosine kinase inhibitor", "Inhibits BCR-ABL, KIT, and PDGFR tyrosine kinases."),
    ("Erlotinib", "Erlotinib hydrochloride", "Tyrosine kinase inhibitor", "Inhibits the EGFR tyrosine kinase domain."),
    ("Gefitinib", "Gefitinib", "Tyrosine kinase inhibitor", "Inhibits the EGFR tyrosine kinase domain."),
    ("Sorafenib", "Sorafenib tosylate", "Multikinase inhibitor", "Inhibits VEGFR, PDGFR, and RAF kinases."),
    ("Sunitinib", "Sunitinib malate", "Multikinase inhibitor", "Inhibits VEGFR, PDGFR, and KIT."),
    ("Tamoxifen", "Tamoxifen citrate", "Selective estrogen receptor modulator", "Competitively binds estrogen receptors."),
    ("Anastrozole", "Anastrozole", "Aromatase inhibitor", "Inhibits aromatase, reducing estrogen synthesis."),
    ("Letrozole", "Letrozole", "Aromatase inhibitor", "Inhibits aromatase, reducing estrogen synthesis."),
    ("Cisplatin", "Cisplatin", "Platinum chemotherapy", "Crosslinks DNA, inducing apoptosis in rapidly dividing cells."),
    ("Paclitaxel", "Paclitaxel", "Taxane chemotherapy", "Stabilizes microtubules, blocking mitosis."),
    ("Doxorubicin", "Doxorubicin hydrochloride", "Anthracycline chemotherapy", "Intercalates DNA and inhibits topoisomerase II."),
    ("Vincristine", "Vincristine sulfate", "Vinca alkaloid chemotherapy", "Binds tubulin, inhibiting microtubule formation."),
    ("Donepezil", "Donepezil hydrochloride", "Acetylcholinesterase inhibitor", "Inhibits acetylcholinesterase, increasing synaptic acetylcholine."),
    ("Memantine", "Memantine hydrochloride", "NMDA receptor antagonist", "Blocks NMDA glutamate receptors."),
    ("Levodopa", "Levodopa/carbidopa", "Dopamine precursor", "Converted to dopamine in the CNS, replenishing striatal dopamine."),
    ("Riluzole", "Riluzole", "Glutamate release inhibitor", "Reduces glutamatergic neurotransmission."),
    ("Baclofen", "Baclofen", "GABA-B receptor agonist", "Activates GABA-B receptors, reducing muscle spasticity."),
    ("Diazepam", "Diazepam", "Benzodiazepine", "Enhances GABA-A receptor activity."),
    ("Lorazepam", "Lorazepam", "Benzodiazepine", "Enhances GABA-A receptor activity."),
    ("Albuterol", "Albuterol sulfate", "Beta-2 agonist bronchodilator", "Relaxes bronchial smooth muscle via beta-2 receptor activation."),
    ("Montelukast", "Montelukast sodium", "Leukotriene receptor antagonist", "Blocks the CysLT1 leukotriene receptor."),
    ("Budesonide", "Budesonide", "Inhaled corticosteroid", "Local anti-inflammatory action in airway tissue."),
    ("Fluticasone", "Fluticasone propionate", "Inhaled corticosteroid", "Local anti-inflammatory action in airway tissue."),
    ("Tiotropium", "Tiotropium bromide", "Anticholinergic bronchodilator", "Blocks muscarinic M3 receptors in airway smooth muscle."),
    ("Ranitidine", "Ranitidine", "H2 receptor antagonist", "Blocks histamine H2 receptors in gastric parietal cells."),
    ("Loperamide", "Loperamide hydrochloride", "Opioid receptor agonist (gut)", "Activates mu-opioid receptors in the gut wall, slowing motility."),
    ("Ondansetron", "Ondansetron hydrochloride", "5-HT3 receptor antagonist", "Blocks serotonin 5-HT3 receptors centrally and peripherally."),
    ("Metoclopramide", "Metoclopramide", "Dopamine antagonist / prokinetic", "Blocks dopamine D2 receptors and enhances GI motility."),
    ("Tamsulosin", "Tamsulosin hydrochloride", "Alpha-1 blocker", "Selectively blocks alpha-1A adrenergic receptors in the prostate."),
    ("Finasteride", "Finasteride", "5-alpha reductase inhibitor", "Inhibits conversion of testosterone to dihydrotestosterone."),
    ("Sildenafil", "Sildenafil citrate", "PDE5 inhibitor", "Inhibits phosphodiesterase type 5, increasing cGMP."),
    ("Tadalafil", "Tadalafil", "PDE5 inhibitor", "Inhibits phosphodiesterase type 5, increasing cGMP."),
    ("Naloxone", "Naloxone hydrochloride", "Opioid receptor antagonist", "Competitively blocks mu-opioid receptors."),
    ("Buprenorphine", "Buprenorphine", "Partial opioid agonist", "Partial agonist at the mu-opioid receptor."),
    ("Insulin lispro", "Insulin lispro", "Rapid-acting insulin analog", "Rapid-onset insulin receptor agonist."),
    ("Empagliflozin", "Empagliflozin", "SGLT2 inhibitor", "Inhibits sodium-glucose cotransporter 2 in the renal tubule."),
    ("Sitagliptin", "Sitagliptin phosphate", "DPP-4 inhibitor", "Inhibits dipeptidyl peptidase-4, prolonging incretin activity."),
    ("Liraglutide", "Liraglutide", "GLP-1 receptor agonist", "Activates the GLP-1 receptor, enhancing insulin secretion."),
    ("Semaglutide", "Semaglutide", "GLP-1 receptor agonist", "Activates the GLP-1 receptor, enhancing insulin secretion."),
    ("Pioglitazone", "Pioglitazone hydrochloride", "Thiazolidinedione", "Activates PPAR-gamma, improving insulin sensitivity."),
    ("Rifampin", "Rifampin", "Antimycobacterial", "Inhibits bacterial DNA-dependent RNA polymerase."),
    ("Isoniazid", "Isoniazid", "Antimycobacterial", "Inhibits mycolic acid synthesis in mycobacteria."),
    ("Acyclovir", "Acyclovir", "Antiviral (nucleoside analog)", "Inhibits viral DNA polymerase after phosphorylation."),
    ("Oseltamivir", "Oseltamivir phosphate", "Neuraminidase inhibitor", "Inhibits the influenza neuraminidase enzyme."),
    ("Ritonavir", "Ritonavir", "Protease inhibitor", "Inhibits HIV-1 protease and boosts other protease inhibitors via CYP3A4."),
    ("Tenofovir", "Tenofovir disoproxil fumarate", "Nucleotide reverse transcriptase inhibitor", "Inhibits HIV reverse transcriptase."),
    ("Remdesivir", "Remdesivir", "Nucleotide analog antiviral", "Inhibits viral RNA-dependent RNA polymerase."),
    ("Colchicine", "Colchicine", "Anti-inflammatory (microtubule)", "Inhibits microtubule polymerization, reducing neutrophil activity."),
    ("Febuxostat", "Febuxostat", "Xanthine oxidase inhibitor", "Selectively inhibits xanthine oxidase."),
    ("Duloxetine", "Duloxetine hydrochloride", "SNRI", "Inhibits serotonin and norepinephrine reuptake."),
    ("Venlafaxine", "Venlafaxine hydrochloride", "SNRI", "Inhibits serotonin and norepinephrine reuptake."),
    ("Bupropion", "Bupropion hydrochloride", "NDRI", "Inhibits norepinephrine and dopamine reuptake."),
    ("Quetiapine", "Quetiapine fumarate", "Atypical antipsychotic", "Antagonizes dopamine D2 and serotonin 5-HT2A receptors."),
    ("Risperidone", "Risperidone", "Atypical antipsychotic", "Antagonizes dopamine D2 and serotonin 5-HT2A receptors."),
    ("Olanzapine", "Olanzapine", "Atypical antipsychotic", "Antagonizes dopamine D2 and serotonin 5-HT2A receptors."),
    ("Aripiprazole", "Aripiprazole", "Atypical antipsychotic", "Partial agonist at dopamine D2 and serotonin 5-HT1A receptors."),
    ("Lithium carbonate", "Lithium carbonate", "Mood stabilizer", "Modulates inositol monophosphatase and GSK-3 signaling."),
    ("Valproate", "Valproic acid", "Anticonvulsant/mood stabilizer", "Enhances GABAergic transmission and blocks sodium channels."),
    ("Lamotrigine", "Lamotrigine", "Anticonvulsant", "Blocks voltage-gated sodium channels."),
    ("Topiramate", "Topiramate", "Anticonvulsant", "Blocks sodium channels and enhances GABA activity."),
    ("Carbamazepine", "Carbamazepine", "Anticonvulsant", "Blocks voltage-gated sodium channels."),
    ("Phenytoin", "Phenytoin sodium", "Anticonvulsant", "Blocks voltage-gated sodium channels."),
]

DISEASE_CATALOG = [
    ("Type 2 Diabetes Mellitus", "Metabolic", "Chronic condition of insulin resistance and hyperglycemia."),
    ("Essential Hypertension", "Cardiovascular", "Chronic elevation of arterial blood pressure without a clear secondary cause."),
    ("Coronary Artery Disease", "Cardiovascular", "Atherosclerotic narrowing of the coronary arteries."),
    ("Rheumatoid Arthritis", "Autoimmune", "Chronic autoimmune inflammatory joint disease."),
    ("Systemic Lupus Erythematosus", "Autoimmune", "Multisystem autoimmune disease with autoantibody production."),
    ("Alzheimer's Disease", "Neurodegenerative", "Progressive neurodegeneration causing dementia."),
    ("Parkinson's Disease", "Neurodegenerative", "Progressive loss of dopaminergic neurons causing motor symptoms."),
    ("Amyotrophic Lateral Sclerosis", "Neurodegenerative", "Progressive motor neuron degeneration."),
    ("Multiple Sclerosis", "Autoimmune/Neurological", "Autoimmune demyelination of the central nervous system."),
    ("Major Depressive Disorder", "Psychiatric", "Persistent low mood and loss of interest impairing function."),
    ("Generalized Anxiety Disorder", "Psychiatric", "Chronic, excessive anxiety and worry."),
    ("Bipolar Disorder", "Psychiatric", "Recurrent episodes of mania and depression."),
    ("Schizophrenia", "Psychiatric", "Chronic psychotic disorder affecting thought and perception."),
    ("Asthma", "Respiratory", "Chronic airway inflammation causing reversible obstruction."),
    ("Chronic Obstructive Pulmonary Disease", "Respiratory", "Progressive, largely irreversible airflow limitation."),
    ("Idiopathic Pulmonary Fibrosis", "Respiratory", "Progressive scarring of lung tissue of unknown cause."),
    ("Non-Small Cell Lung Cancer", "Oncology", "The most common histological subtype of lung cancer."),
    ("Breast Cancer", "Oncology", "Malignant neoplasm arising from breast tissue."),
    ("Colorectal Cancer", "Oncology", "Malignant neoplasm of the colon or rectum."),
    ("Pancreatic Cancer", "Oncology", "Aggressive malignant neoplasm of the pancreas."),
    ("Prostate Cancer", "Oncology", "Malignant neoplasm of the prostate gland."),
    ("Chronic Myeloid Leukemia", "Oncology", "Myeloproliferative neoplasm driven by the BCR-ABL fusion."),
    ("Acute Lymphoblastic Leukemia", "Oncology", "Acute malignancy of lymphoid precursor cells."),
    ("Melanoma", "Oncology", "Malignant neoplasm of melanocytes."),
    ("Glioblastoma", "Oncology", "Aggressive malignant primary brain tumor."),
    ("Chronic Kidney Disease", "Renal", "Progressive loss of kidney function over time."),
    ("Nonalcoholic Fatty Liver Disease", "Hepatic", "Excess fat accumulation in the liver unrelated to alcohol use."),
    ("Cirrhosis", "Hepatic", "End-stage liver fibrosis and dysfunction."),
    ("Inflammatory Bowel Disease", "Gastrointestinal", "Chronic inflammatory disease of the GI tract (Crohn's/UC)."),
    ("Irritable Bowel Syndrome", "Gastrointestinal", "Functional GI disorder with abdominal pain and altered bowel habits."),
    ("Gastroesophageal Reflux Disease", "Gastrointestinal", "Chronic reflux of gastric contents into the esophagus."),
    ("Osteoarthritis", "Musculoskeletal", "Degenerative joint disease from cartilage breakdown."),
    ("Osteoporosis", "Musculoskeletal", "Reduced bone mineral density increasing fracture risk."),
    ("Gout", "Musculoskeletal", "Inflammatory arthritis from urate crystal deposition."),
    ("Psoriasis", "Dermatological", "Chronic autoimmune skin disease with keratinocyte hyperproliferation."),
    ("Atopic Dermatitis", "Dermatological", "Chronic relapsing inflammatory skin condition."),
    ("HIV/AIDS", "Infectious", "Chronic viral infection targeting CD4+ T cells."),
    ("Tuberculosis", "Infectious", "Chronic bacterial infection caused by Mycobacterium tuberculosis."),
    ("Influenza", "Infectious", "Acute viral respiratory infection."),
    ("COVID-19", "Infectious", "Acute respiratory illness caused by SARS-CoV-2."),
    ("Malaria", "Infectious", "Parasitic infection transmitted by Anopheles mosquitoes."),
    ("Migraine", "Neurological", "Recurrent moderate-to-severe headache disorder."),
    ("Epilepsy", "Neurological", "Chronic disorder of recurrent unprovoked seizures."),
    ("Stroke", "Cardiovascular/Neurological", "Acute disruption of cerebral blood flow."),
    ("Heart Failure", "Cardiovascular", "Impaired cardiac pump function causing congestion and fatigue."),
    ("Atrial Fibrillation", "Cardiovascular", "Irregular, often rapid, atrial heart rhythm."),
    ("Deep Vein Thrombosis", "Cardiovascular", "Blood clot formation in a deep vein, typically the leg."),
    ("Chronic Lymphocytic Leukemia", "Oncology", "Indolent malignancy of mature B lymphocytes."),
    ("Ovarian Cancer", "Oncology", "Malignant neoplasm of the ovary."),
    ("Endometriosis", "Gynecological", "Growth of endometrial-like tissue outside the uterus."),
    ("Polycystic Ovary Syndrome", "Endocrine", "Hormonal disorder causing irregular cycles and hyperandrogenism."),
    ("Hypothyroidism", "Endocrine", "Underactive thyroid hormone production."),
    ("Hyperthyroidism", "Endocrine", "Overactive thyroid hormone production."),
    ("Obesity", "Metabolic", "Excess adiposity associated with metabolic and cardiovascular risk."),
    ("Metabolic Syndrome", "Metabolic", "Cluster of insulin resistance, hypertension, and dyslipidemia."),
]

# Curated well-known human gene symbols spanning several disease areas.
GENE_CATALOG = [
    "TP53", "BRCA1", "BRCA2", "EGFR", "KRAS", "MYC", "PTEN", "RB1", "APC", "PIK3CA",
    "BRAF", "ALK", "ERBB2", "MET", "ABL1", "BCR", "JAK2", "FLT3", "NPM1", "IDH1",
    "IDH2", "VHL", "MLH1", "MSH2", "MSH6", "PMS2", "CDKN2A", "SMAD4", "STK11", "NOTCH1",
    "APOE", "PSEN1", "PSEN2", "APP", "MAPT", "SNCA", "LRRK2", "PARK7", "PINK1", "GBA",
    "SOD1", "TARDBP", "FUS", "C9orf72", "HTT", "ATXN1", "DMPK", "FMR1", "MECP2", "SHANK3",
    "INS", "INSR", "GCK", "HNF1A", "HNF4A", "PPARG", "TCF7L2", "KCNJ11", "ABCC8", "SLC2A4",
    "LDLR", "APOB", "PCSK9", "APOA1", "CETP", "LPA", "NOS3", "ACE", "AGT", "AGTR1",
    "REN", "NPPA", "NPPB", "MYH7", "MYBPC3", "TNNT2", "SCN5A", "KCNQ1", "KCNH2", "RYR2",
    "HLA-DRB1", "HLA-B", "PTPN22", "CTLA4", "IL2RA", "STAT4", "IRF5", "TNFAIP3", "TYK2", "IL23R",
    "NOD2", "ATG16L1", "IL10", "TNF", "IL6", "IL1B", "NFKB1", "TLR4", "CRP", "VEGFA",
    "CFTR", "SERPINA1", "SFTPC", "MUC5B", "TERT", "TERC", "DSP", "ITGB4", "COL1A1", "COL4A5",
    "FBN1", "DMD", "SMN1", "SMN2", "ATM", "CHEK2", "PALB2", "RAD51C", "BARD1", "MUTYH",
]

TARGET_TYPES = ["protein", "enzyme", "receptor", "ion_channel", "transporter"]

USER_NAME_ROLES = [
    ("Dr. Elena Vasquez", RoleName.RESEARCHER),
    ("Dr. Marcus Chen", RoleName.RESEARCHER),
    ("Dr. Priya Sharma", RoleName.RESEARCHER),
    ("Sofia Almeida", RoleName.ANALYST),
    ("James Okafor", RoleName.ANALYST),
    ("Wei Zhang", RoleName.ANALYST),
    ("Laura Fontaine", RoleName.VIEWER),
    ("Tomás Ibarra", RoleName.VIEWER),
]


def utcnow():
    return datetime.now(timezone.utc)


def seed_users(db: Session) -> list[User]:
    users = []
    for name, role_enum in USER_NAME_ROLES:
        role = get_or_create_role(db, role_enum.value)
        email = name.lower().replace("dr. ", "").replace(" ", ".").replace("á", "a").replace("é", "e") + "@repurpose.ai"
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            users.append(existing)
            continue
        user = User(name=name, email=email, password_hash=hash_password("Demo1234!"), role_id=role.id, is_active=True)
        db.add(user)
        db.flush()
        users.append(user)
    return users


def seed_biotech_entities(db: Session) -> dict:
    genes = []
    for symbol in GENE_CATALOG:
        gene = Gene(
            symbol=symbol,
            name=f"{symbol} gene",
            organism="Homo sapiens",
            identifiers={"hgnc": symbol},
            extra_metadata=DEMO_META,
        )
        db.add(gene)
        genes.append(gene)
    db.flush()

    targets = []
    for gene in genes:
        for _ in range(random.randint(1, 2)):
            target = Target(
                name=f"{gene.symbol} {random.choice(['protein', 'kinase domain', 'receptor complex'])}",
                target_type=random.choice(TARGET_TYPES),
                gene_id=gene.id,
                description=f"Target derived from {gene.symbol} for demonstration purposes.",
                extra_metadata=DEMO_META,
            )
            db.add(target)
            targets.append(target)
    db.flush()

    diseases = []
    for name, category, description in DISEASE_CATALOG:
        disease = Disease(
            name=name, description=description, category=category,
            identifiers={"demo_id": name.lower().replace(" ", "-")},
            extra_metadata=DEMO_META,
        )
        db.add(disease)
        diseases.append(disease)
    db.flush()

    drugs = []
    for name, generic_name, drug_class, mechanism in DRUG_CATALOG:
        drug = Drug(
            name=name, generic_name=generic_name, drug_class=drug_class, mechanism=mechanism,
            approval_status=random.choice(["approved", "approved", "approved", "investigational"]),
            extra_metadata=DEMO_META,
        )
        db.add(drug)
        drugs.append(drug)
    db.flush()

    compounds = []
    for drug in drugs:
        for i in range(random.randint(1, 2)):
            compound = Compound(
                name=f"{drug.name} compound {i + 1}" if i else drug.name,
                drug_id=drug.id,
                smiles=f"C{random.randint(1,20)}H{random.randint(1,30)}N{random.randint(0,4)}O{random.randint(0,6)}",
                molecular_formula=f"C{random.randint(6,40)}H{random.randint(6,60)}N{random.randint(0,6)}O{random.randint(0,10)}",
                molecular_weight=round(random.uniform(150, 650), 2),
                properties={
                    "logp": round(random.uniform(-2, 6), 2),
                    "h_bond_donors": random.randint(0, 6),
                    "h_bond_acceptors": random.randint(0, 10),
                    "polar_surface_area": round(random.uniform(10, 140), 1),
                    "rotatable_bonds": random.randint(0, 12),
                },
                extra_metadata=DEMO_META,
            )
            db.add(compound)
            compounds.append(compound)
    db.flush()

    interactions = []

    # gene <-> disease associations
    for disease in diseases:
        for gene in random.sample(genes, k=random.randint(3, 8)):
            interactions.append(Interaction(
                source_entity=f"gene:{gene.symbol}", target_entity=f"disease:{disease.name}",
                source_type="gene", source_id=str(gene.id), target_type="disease", target_id=str(disease.id),
                interaction_type="gene_disease",
                confidence_score=round(random.uniform(0.3, 0.95), 3),
                evidence={"note": "Synthetic association for demo purposes.", **DEMO_META},
                extra_metadata=DEMO_META,
            ))

    # drug <-> target associations
    for drug in drugs:
        for target in random.sample(targets, k=random.randint(1, 4)):
            interactions.append(Interaction(
                source_entity=f"drug:{drug.name}", target_entity=f"target:{target.name}",
                source_type="drug", source_id=str(drug.id), target_type="target", target_id=str(target.id),
                interaction_type="drug_target",
                confidence_score=round(random.uniform(0.4, 0.97), 3),
                evidence={"note": "Synthetic drug-target binding evidence for demo purposes.", **DEMO_META},
                extra_metadata=DEMO_META,
            ))

    # a smaller number of direct drug <-> disease ("known indication") links,
    # used as reference points by the compound-similarity scorer.
    for drug in random.sample(drugs, k=30):
        disease = random.choice(diseases)
        interactions.append(Interaction(
            source_entity=f"drug:{drug.name}", target_entity=f"disease:{disease.name}",
            source_type="drug", source_id=str(drug.id), target_type="disease", target_id=str(disease.id),
            interaction_type="drug_disease",
            confidence_score=round(random.uniform(0.6, 0.99), 3),
            evidence={"note": "Synthetic known-indication reference for demo purposes.", **DEMO_META},
            extra_metadata=DEMO_META,
        ))

    db.add_all(interactions)
    db.flush()

    return {"genes": genes, "targets": targets, "diseases": diseases, "drugs": drugs, "compounds": compounds, "interactions": interactions}


PROJECT_TOPICS = [
    "Repurposing Candidates for {d}", "Gene Signature Analysis in {d}", "Target Discovery for {d}",
    "Compound Screening Program: {d}", "Evidence Review for {d}", "Biomarker Study in {d}",
]


def seed_projects(db: Session, users: list[User], diseases: list[Disease], count: int = 24) -> list[Project]:
    projects = []
    owners = [u for u in users if u.role.name in ("researcher", "analyst")]
    for i in range(count):
        disease = diseases[i % len(diseases)]
        topic = random.choice(PROJECT_TOPICS).format(d=disease.name)
        owner = owners[i % len(owners)]
        project = Project(
            owner_id=owner.id, name=topic,
            description=f"Computational research project investigating {disease.name.lower()} using platform demo data.",
            status=random.choice([ProjectStatus.ACTIVE.value] * 3 + [ProjectStatus.COMPLETED.value, ProjectStatus.ON_HOLD.value]),
        )
        db.add(project)
        projects.append(project)
    db.flush()
    return projects


def _build_demo_dataset_csv(genes: list[Gene]) -> tuple[str, bytes]:
    import io
    import csv

    sample_genes = random.sample(genes, k=min(30, len(genes)))
    samples = [f"sample_{i+1}" for i in range(8)]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["gene_symbol", *samples])
    for gene in sample_genes:
        row = [gene.symbol] + [round(random.uniform(0, 15), 3) for _ in samples]
        writer.writerow(row)
    content = buf.getvalue().encode("utf-8")
    return "gene_expression_demo.csv", content


def seed_datasets(db: Session, projects: list[Project], genes: list[Gene], count: int = 26) -> list[Dataset]:
    from app.utils.file_utils import build_dataset_storage_key, get_storage

    storage = get_storage()
    datasets = []
    for i in range(count):
        project = projects[i % len(projects)]
        dataset = Dataset(
            project_id=project.id, name=f"Gene expression panel #{i + 1}",
            description="Synthetic demo gene expression matrix (genes x samples).",
            file_name="gene_expression_demo.csv", file_type="csv", file_size=0,
            storage_path="", status=DatasetStatus.UPLOADED.value,
        )
        db.add(dataset)
        db.flush()

        file_name, content = _build_demo_dataset_csv(genes)
        key = build_dataset_storage_key(str(project.id), str(dataset.id), file_name)
        storage.save(content, key)

        from app.ai.preprocessing.preprocessing import compute_dataframe_metadata
        from app.data.loaders.dataset_loader import load_dataframe

        df = load_dataframe(content, "csv")
        metadata = compute_dataframe_metadata(df)

        dataset.storage_path = key
        dataset.file_size = len(content)
        dataset.row_count = metadata["row_count"]
        dataset.column_count = metadata["column_count"]
        dataset.extra_metadata = {**metadata, **DEMO_META}
        dataset.status = DatasetStatus.VALID.value
        datasets.append(dataset)
    db.flush()
    return datasets


def seed_experiments_and_predictions(db: Session, projects: list[Project], diseases: list[Disease], datasets: list[Dataset]) -> dict:
    """
    Creates demo experiments across a spread of statuses/types. For a subset of
    'drug_repurposing' experiments, this calls the *real* AI pipeline
    (app.biotech.drug_repurposing.run_repurposing_analysis) so the seeded
    predictions are genuinely computed, not fabricated.
    """
    from app.biotech.drug_repurposing import run_repurposing_analysis
    from app.models.analysis import Analysis
    from app.models.prediction import Prediction

    experiments = []
    total_predictions = 0
    repurposing_diseases = random.sample(diseases, k=min(12, len(diseases)))

    for i in range(56):
        project = projects[i % len(projects)]
        if i < len(repurposing_diseases):
            disease = repurposing_diseases[i]
            exp_type = ExperimentType.DRUG_REPURPOSING
            params = {"disease_id": str(disease.id), "top_k": 15}
        else:
            exp_type = random.choice([ExperimentType.GENE_EXPRESSION, ExperimentType.TARGET_ANALYSIS, ExperimentType.CUSTOM])
            params = {"dataset_id": str(random.choice(datasets).id)} if exp_type != ExperimentType.CUSTOM else {}

        status = random.choice(
            [ExperimentStatus.COMPLETED] * 5 + [ExperimentStatus.FAILED, ExperimentStatus.RUNNING, ExperimentStatus.DRAFT]
        )
        if exp_type == ExperimentType.DRUG_REPURPOSING:
            status = ExperimentStatus.COMPLETED  # always compute these for real, demo-visible predictions

        experiment = Experiment(
            project_id=project.id, name=f"{exp_type.value.replace('_', ' ').title()} run #{i + 1}",
            description="Demo experiment seeded for platform evaluation.",
            experiment_type=exp_type.value, status=status.value, parameters=params,
            progress=100 if status == ExperimentStatus.COMPLETED else random.randint(0, 60),
            started_at=utcnow() - timedelta(days=random.randint(0, 30)),
            completed_at=utcnow() - timedelta(days=random.randint(0, 29)) if status in (ExperimentStatus.COMPLETED, ExperimentStatus.FAILED) else None,
        )
        db.add(experiment)
        db.flush()
        experiments.append(experiment)

        if exp_type == ExperimentType.DRUG_REPURPOSING and status == ExperimentStatus.COMPLETED:
            try:
                result = run_repurposing_analysis(db, disease.id, top_k=15)
            except Exception:
                continue

            db.add(Analysis(
                experiment_id=experiment.id, analysis_type="drug_repurposing", status="COMPLETED", progress=100,
                parameters=params, results={"candidate_pool_size": result["candidate_pool_size"], "prediction_count": len(result["results"])},
                started_at=experiment.started_at, completed_at=experiment.completed_at,
            ))
            for item in result["results"]:
                db.add(Prediction(
                    project_id=project.id, experiment_id=experiment.id,
                    drug_id=uuid.UUID(item["drug_id"]), disease_id=disease.id,
                    score=item["score"], confidence=item["confidence"], rank=item["rank"],
                    explanation=item["explanation"], features=item["features"], model_version=item["model_version"],
                ))
                total_predictions += 1
            db.flush()

    return {"experiments": experiments, "prediction_count": total_predictions}


def seed_notifications(db: Session, users: list[User], count: int = 34) -> int:
    from app.services.notification_service import create_notification

    templates = [
        (NotificationType.EXPERIMENT_COMPLETED, "Experiment completed", "Your experiment finished successfully."),
        (NotificationType.EXPERIMENT_FAILED, "Experiment failed", "Your experiment failed during execution."),
        (NotificationType.ANALYSIS_COMPLETED, "Analysis completed", "Your analysis job has finished."),
        (NotificationType.PREDICTION_GENERATED, "Predictions ready", "New repurposing predictions are available."),
        (NotificationType.HIGH_CONFIDENCE_CANDIDATE, "High-confidence candidate found", "A high-confidence repurposing candidate was identified."),
        (NotificationType.DATASET_VALIDATION_FAILED, "Dataset validation failed", "One of your datasets failed validation checks."),
    ]
    created = 0
    for i in range(count):
        user = users[i % len(users)]
        n_type, title, message = templates[i % len(templates)]
        create_notification(db, user.id, title, message, n_type, {"seed_index": i, **DEMO_META})
        created += 1
    db.flush()
    return created


def seed_recommendations(db: Session, users: list[User]) -> int:
    from app.services.recommendation_service import generate_recommendations

    total = 0
    for user in users:
        if user.role.name in ("researcher", "analyst"):
            recs = generate_recommendations(db, user)
            total += len(recs)
    db.flush()
    return total
