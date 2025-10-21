// web_platform/frontend/app/layout.tsx
import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { Providers } from '../src/components/Providers'; // Import the new provider component

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Checkmate Live',
  description: 'Real-time horse racing analysis.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}