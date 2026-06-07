/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { brand: { DEFAULT: "#155eef", dark: "#0e47c4" } },
    },
    screens: { lg: "1024px", xl: "1280px", "2xl": "1536px" }, // B-end min width 1024px
  },
  plugins: [],
};
