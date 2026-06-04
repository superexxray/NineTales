import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                primary: {
                    400: '#5252b8',
                    500: '#333394', // Core primary color
                    600: '#2b2b7d',
                },
                accent: {
                    400: '#fd7a63',
                    500: '#fc5639', // Core accent color
                    600: '#e64e33',
                },
                background: '#f8fafc',
            },
            backgroundImage: {
                "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
                "gradient-conic":
                    "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
            },
            fontFamily: {
                sans: ['var(--font-inter)', 'sans-serif'],
            }
        },
    },
    plugins: [],
};
export default config;
