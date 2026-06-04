import * as z from 'zod';

export const onboardingSchema = z.object({
    // Step 1: Entity Information
    companyName: z.string().min(2, "Company Name must be at least 2 characters").max(100),
    cin: z.string().regex(/^[A-Z0-9]{21}$/, "CIN must be a 21-character alphanumeric string"),
    pan: z.string().regex(/^[A-Z]{5}[0-9]{4}[A-Z]{1}$/, "Invalid PAN format"),
    sector: z.string().min(2, "Sector is required"),
    subsector: z.string().min(2, "Subsector is required"),

    // Step 2: Financial Overview
    annualTurnover: z.number({
        required_error: "Annual Turnover is required",
        invalid_type_error: "Must be a number",
    }).positive("Must be greater than 0"),
    netProfit: z.number({
        required_error: "Net Profit is required",
        invalid_type_error: "Must be a number",
    }),
    totalDebt: z.number({
        required_error: "Total Debt is required",
        invalid_type_error: "Must be a number",
    }).nonnegative("Cannot be negative"),
    ebitda: z.number({
        required_error: "EBITDA is required",
        invalid_type_error: "Must be a number",
    }),

    // Step 3: Loan Request
    loanType: z.enum(['Term Loan', 'Working Capital', 'Revolving Credit'], {
        errorMap: () => ({ message: "Please select a valid Loan Type" })
    }),
    loanAmount: z.number({
        required_error: "Loan Amount is required",
        invalid_type_error: "Must be a number",
    }).positive("Must be greater than 0"),
    loanTenure: z.number({
        required_error: "Loan Tenure is required",
        invalid_type_error: "Must be a number",
    }).int().positive("Tenure must be in months (> 0)"),
    expectedInterestRate: z.number({
        required_error: "Expected Interest Rate is required",
        invalid_type_error: "Must be a number",
    }).min(0.1, "Must be > 0.1").max(50, "Unrealistic interest rate"),
});

export type OnboardingFormData = z.infer<typeof onboardingSchema>;
