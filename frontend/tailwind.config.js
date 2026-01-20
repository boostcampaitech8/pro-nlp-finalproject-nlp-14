/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      // 디자인 문서 기준 색상
      colors: {
        // Mit 브랜드 색상
        'mit-primary': '#3b82f6',
        'mit-purple': '#8b5cf6',
        'mit-success': '#22c55e',
        'mit-warning': '#ef4444',

        // shadcn/ui 색상 변수
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
      },

      // 글래스모피즘 배경
      backgroundColor: {
        glass: 'rgba(255, 255, 255, 0.7)',
        'glass-dark': 'rgba(30, 41, 59, 0.5)',
        'glass-darker': 'rgba(15, 23, 42, 0.8)',
        'card-bg': 'rgba(30, 41, 59, 0.5)',
        'card-hover': 'rgba(30, 41, 59, 0.8)',
        'input-bg': 'rgba(30, 41, 59, 0.8)',
      },

      // 글래스모피즘 테두리
      borderColor: {
        glass: 'rgba(255, 255, 255, 0.08)',
        'glass-light': 'rgba(255, 255, 255, 0.1)',
        'glass-active': 'rgba(59, 130, 246, 0.3)',
      },

      // 글래스모피즘 그림자
      boxShadow: {
        glass: '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
        'glass-lg': '0 8px 40px 0 rgba(31, 38, 135, 0.47)',
        'input-focus': '0 0 0 4px rgba(59, 130, 246, 0.1)',
      },

      // 블러 효과
      backdropBlur: {
        xs: '2px',
      },

      // 텍스트 색상
      textColor: {
        'white-60': 'rgba(255, 255, 255, 0.6)',
        'white-40': 'rgba(255, 255, 255, 0.4)',
        'white-50': 'rgba(255, 255, 255, 0.5)',
      },

      // 테두리 둥글기
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },

      // 애니메이션
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'fade-out': {
          from: { opacity: '1' },
          to: { opacity: '0' },
        },
        'slide-in-from-top': {
          from: { transform: 'translateY(-10px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
        'slide-in-from-bottom': {
          from: { transform: 'translateY(10px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
        'slide-in-from-left': {
          from: { transform: 'translateX(-10px)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        'slide-in-from-right': {
          from: { transform: 'translateX(10px)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        'message-in-left': {
          from: { transform: 'translateX(-20px) scale(0.95)', opacity: '0' },
          to: { transform: 'translateX(0) scale(1)', opacity: '1' },
        },
        'message-in-right': {
          from: { transform: 'translateX(20px) scale(0.95)', opacity: '0' },
          to: { transform: 'translateX(0) scale(1)', opacity: '1' },
        },
        'typing-dot': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
        'fade-out': 'fade-out 0.2s ease-out',
        'slide-in-from-top': 'slide-in-from-top 0.2s ease-out',
        'slide-in-from-bottom': 'slide-in-from-bottom 0.2s ease-out',
        'slide-in-from-left': 'slide-in-from-left 0.2s ease-out',
        'slide-in-from-right': 'slide-in-from-right 0.2s ease-out',
        'message-in-left': 'message-in-left 0.3s cubic-bezier(0.32, 0.72, 0, 1)',
        'message-in-right': 'message-in-right 0.3s cubic-bezier(0.32, 0.72, 0, 1)',
        'typing-dot': 'typing-dot 0.6s ease-in-out infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
