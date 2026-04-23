/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      colors: {
        // AIRIS Primary (Blue)
        primary: {
          50: "#EFF6FF",
          100: "#DBEAFE",
          200: "#BFDBFE",
          300: "#93C5FD",
          400: "#60A5FA",
          500: "#3B82F6",
          600: "#2563EB",
          700: "#1D4ED8",
          800: "#1E40AF",
          900: "#1E3A5F",
        },
        // Neutral (Slate with blue tint)
        neutral: {
          0: "#FFFFFF",
          50: "#F0F5FA",
          100: "#E8EDF4",
          200: "#DEE2E8",
          300: "#BFC4CC",
          400: "#949AA4",
          500: "#6B7280",
          600: "#525B67",
          700: "#3A4250",
          800: "#262E3B",
          900: "#141A23",
        },
        // Semantic
        success: {
          50: "#ECFDF5",
          500: "#10B981",
          700: "#047857",
        },
        warning: {
          50: "#FFFBEB",
          500: "#F59E0B",
          700: "#B45309",
        },
        error: {
          50: "#FEF2F2",
          500: "#EF4444",
          700: "#B91C1C",
        },
        info: {
          50: "#EFF6FF",
          500: "#3B82F6",
        },
        // AIRIS-specific
        urgency: {
          standard: "#6B7280",
          urgent: "#F59E0B",
          critical: "#EF4444",
        },
        // Pipeline stage colours
        stage: {
          screening: "#10B981",
          interview: "#3B82F6",
          test: "#8B5CF6",
          offer: "#F59E0B",
          hired: "#EF4444",
        },
        // Star rating
        star: {
          filled: "#F59E0B",
          unfilled: "#DEE2E8",
        },
        // shadcn/ui CSS variable mappings
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
      },
      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(0, 0, 0, 0.05)",
        md: "0 4px 6px rgba(0, 0, 0, 0.07)",
        lg: "0 10px 15px rgba(0, 0, 0, 0.1)",
      },
      maxWidth: {
        content: "1280px",
      },
      width: {
        sidebar: "240px",
        "sidebar-collapsed": "64px",
        "pipeline-column": "280px",
        "right-panel": "320px",
      },
      height: {
        topbar: "56px",
      },
      transitionDuration: {
        hover: "150ms",
        modal: "200ms",
        sidebar: "200ms",
        toast: "300ms",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-in-right": {
          "0%": { transform: "translateX(100%)" },
          "100%": { transform: "translateX(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
        "slide-in-right": "slide-in-right 300ms ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};