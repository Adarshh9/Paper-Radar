import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
    title: 'Paper Radar - Discover Academic Research',
    description: 'Academic paper discovery platform that aggregates, ranks, and personalizes research papers from arXiv, Semantic Scholar, and more.',
    keywords: ['research papers', 'arXiv', 'machine learning', 'AI research', 'academic papers'],
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" className="dark">
            <body className={inter.className}>
                <div className="min-h-screen bg-background">
                    {children}
                </div>
            </body>
        </html>
    );
}
