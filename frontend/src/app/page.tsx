import { OnboardingForm } from '@/components/OnboardingForm';

export default function Home() {
    return (
        <div className="w-full">
            {/* Decorative top background */}
            <div className="absolute top-0 inset-x-0 h-64 bg-gradient-to-b from-primary-900 mix-blend-multiply to-transparent opacity-5 z-0"></div>

            <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-10 pb-20">
                <div className="text-center mb-10">
                    <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight sm:text-5xl">
                        New Credit <span className="text-accent-500">Application</span>
                    </h1>
                    <p className="mt-4 max-w-2xl text-lg text-slate-600 mx-auto">
                        Fill out the details below to initiate the credit assessment logic for a new entity.
                        All information will be securely evaluated against compliance standards.
                    </p>
                </div>

                <OnboardingForm />
            </div>
        </div>
    );
}
