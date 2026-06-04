import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({
    subsets: ['latin'],
    variable: '--font-inter',
})

export const metadata: Metadata = {
    title: 'Entity Onboarding | NineTales Credit Underwriting',
    description: 'Onboarding interface for the enterprise credit underwriting system',
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body className={`${inter.variable} font-sans antialiased text-slate-800 bg-slate-50 min-h-screen flex flex-col`}>
                <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded bg-primary-500 flex items-center justify-center">
                                <span className="text-white font-bold text-lg leading-none">N</span>
                            </div>
                            <span className="text-xl font-bold text-primary-500">
                                NineTales
                            </span>
                            <span className="hidden sm:inline-block ml-4 pl-4 border-l border-slate-200 text-sm font-medium text-slate-500">
                                Enterprise Credit Underwriting System
                            </span>
                        </div>
                    </div>
                </header>

                <main className="flex-1 flex flex-col">
                    {children}
                </main>

                <footer className="bg-white border-t border-slate-200 py-6 mt-auto">
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm text-slate-500">
                        &copy; {new Date().getFullYear()} NineTales Enterprise Credit Underwriting System
                    </div>
                </footer>
            </body>
        </html>
    )
}
