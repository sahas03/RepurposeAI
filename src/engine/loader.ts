/**
 * loader.ts
 * Port of repurposeai/src/data_loader.py - CSV parsing, gene harmonisation.
 */
import type { Dataset, DiseaseGene } from './types'

function splitLines(text: string): string[] {
  return text
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .filter((l) => l.length > 0)
}

/** Port of load_disease_signature(): upper-case, de-duplicate, optional top-N by p-value. */
export function parseDiseaseSignature(text: string, topN?: number): DiseaseGene[] {
  const lines = splitLines(text)
  const header = lines[0].split(',').map((h) => h.trim())
  const iGene = header.indexOf('gene')
  const iLog = header.indexOf('logFC')
  const iP = header.indexOf('pvalue')
  const missing = [iGene < 0 && 'gene', iLog < 0 && 'logFC', iP < 0 && 'pvalue'].filter(Boolean)
  if (missing.length) {
    throw new Error(`disease_signature.csv missing columns: ${missing.join(', ')}`)
  }

  const seen = new Set<string>()
  const rows: DiseaseGene[] = []
  for (let i = 1; i < lines.length; i++) {
    const p = lines[i].split(',')
    const gene = (p[iGene] ?? '').trim().toUpperCase()
    const logFC = Number(p[iLog])
    if (!gene || !Number.isFinite(logFC) || seen.has(gene)) continue
    seen.add(gene)
    rows.push({ gene, logFC, pvalue: Number(p[iP]) })
  }

  if (topN != null) {
    rows.sort((a, b) => a.pvalue - b.pvalue)
    return rows.slice(0, topN)
  }
  return rows
}

interface RawMatrix {
  genes: string[]
  drugs: string[]
  rows: Float64Array[]
}

/** Port of load_l1000_matrix(): genes as rows, drugs as columns, dedup index. */
export function parseL1000Matrix(text: string): RawMatrix {
  const lines = splitLines(text)
  const drugs = lines[0]
    .split(',')
    .slice(1)
    .map((d) => d.trim())
  const genes: string[] = []
  const rows: Float64Array[] = []
  const seen = new Set<string>()

  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(',')
    const gene = (parts[0] ?? '').trim().toUpperCase()
    if (!gene || seen.has(gene)) continue
    seen.add(gene)
    const row = new Float64Array(drugs.length)
    for (let j = 0; j < drugs.length; j++) row[j] = Number(parts[j + 1])
    genes.push(gene)
    rows.push(row)
  }
  return { genes, drugs, rows }
}

/**
 * Port of harmonize_genes(): restrict both sides to their shared, sorted gene
 * set. On a real L1000 library this is the step that costs the most genes.
 */
export function harmonize(
  disease: DiseaseGene[],
  raw: RawMatrix,
  meta: { id: string; label: string; provenance: Dataset['provenance'] },
): Dataset {
  const matrixIndex = new Map(raw.genes.map((g, i) => [g, i]))
  const diseaseIndex = new Map(disease.map((d) => [d.gene, d]))
  const shared = [...diseaseIndex.keys()].filter((g) => matrixIndex.has(g)).sort()

  if (shared.length < 20) {
    throw new Error(
      `Only ${shared.length} shared genes found between the disease signature and the ` +
        'drug matrix. Check gene ID formats - both should be HGNC symbols.',
    )
  }

  const nd = raw.drugs.length
  const matrix = new Float64Array(shared.length * nd)
  shared.forEach((g, i) => {
    const src = raw.rows[matrixIndex.get(g)!]
    matrix.set(src, i * nd)
  })

  return {
    ...meta,
    disease: shared.map((g) => diseaseIndex.get(g)!),
    genes: shared,
    drugs: raw.drugs,
    matrix,
    diseaseGenesBefore: disease.length,
    drugsBefore: raw.drugs.length,
  }
}
