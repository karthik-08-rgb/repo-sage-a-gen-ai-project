/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        sage: {
          50: '#f0fdf4',
          100: '#dcfce7',
          500: '#22c55e',
          600: '#16a34a',
          900: '#14532d',
        },
        dark: {
          bg: '#0d1117',
          surface: '#161b22',
          border: '#30363d',
          hover: '#21262d',
          text: '#c9d1d9',
          muted: '#8b949e',
        }
      }
    },
  },
  plugins: [],
}
