export const CATEGORY_STYLES = {
  unverifiable: 'text-amber-300',
  mismatch: 'text-red-300',
  duplicate: 'text-purple-300',
}

export const BLANK_PARTY = { name: '', address: '', tax_id: '', iban: '' }
export const BLANK_LINE_ITEM = {
  description: '',
  unit_price: '',
  quantity: '',
  line_total: '',
  marked: false,
}

export function lineItemHasData(line) {
  return (
    line.description.trim() !== '' ||
    String(line.unit_price).trim() !== '' ||
    String(line.quantity).trim() !== '' ||
    String(line.line_total).trim() !== ''
  )
}

export const BLANK_INVOICE = {
  document_type: 'invoice',
  vendor: { ...BLANK_PARTY },
  customer: { ...BLANK_PARTY },
  invoice_number: '',
  issue_date: '',
  due_date: '',
  currency: '',
  line_items: [{ ...BLANK_LINE_ITEM }],
  grand_total: '',
  subtotal: '',
  tax: '',
  service_charge: '',
  discount: '',
  confidence_notes: [],
}

export function toFormInvoice(invoiceData) {
  if (!invoiceData) return BLANK_INVOICE
  return {
    document_type: invoiceData.document_type ?? 'invoice',
    vendor: invoiceData.vendor
      ? { ...BLANK_PARTY, ...invoiceData.vendor }
      : { ...BLANK_PARTY },
    customer: invoiceData.customer
      ? { ...BLANK_PARTY, ...invoiceData.customer }
      : { ...BLANK_PARTY },
    invoice_number: invoiceData.invoice_number ?? '',
    issue_date: invoiceData.issue_date ?? '',
    due_date: invoiceData.due_date ?? '',
    currency: invoiceData.currency ?? '',
    line_items:
      invoiceData.line_items && invoiceData.line_items.length > 0
        ? invoiceData.line_items.map((line) => ({ ...BLANK_LINE_ITEM, ...line }))
        : [{ ...BLANK_LINE_ITEM }],
    grand_total: invoiceData.grand_total ?? '',
    subtotal: invoiceData.subtotal ?? '',
    tax: invoiceData.tax ?? '',
    service_charge: invoiceData.service_charge ?? '',
    discount: invoiceData.discount ?? '',
    confidence_notes: invoiceData.confidence_notes ?? [],
  }
}