/**
 * Format a number as Indian Rupees (INR).
 * Uses en-IN locale for Indian number grouping (e.g. 1,00,000).
 */
export function formatINR(amount: number): string {
    if (amount == null || !Number.isFinite(amount)) return '₹0';
    return `₹${amount.toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}
