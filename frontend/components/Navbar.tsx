'use client';

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Search, Menu, X, LogIn, User } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores';

interface NavbarProps {
    onSearch?: (query: string) => void;
}

export function Navbar({ onSearch }: NavbarProps) {
    const router = useRouter();
    const [isMenuOpen, setIsMenuOpen] = React.useState(false);
    const [searchQuery, setSearchQuery] = React.useState('');
    const { isAuthenticated, user, logout } = useAuthStore();

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (searchQuery.trim()) {
            router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
        }
    };

    return (
        <nav className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex h-16 items-center justify-between">
                    {/* Logo */}
                    <Link href="/" className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center">
                            <span className="text-white font-bold text-sm">PR</span>
                        </div>
                        <span className="font-bold text-xl text-foreground hidden sm:block">
                            Paper Radar
                        </span>
                    </Link>

                    {/* Search */}
                    <form onSubmit={handleSearch} className="flex-1 max-w-lg mx-4 hidden md:block">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <input
                                type="text"
                                placeholder="Search papers..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full bg-secondary border-0 rounded-lg pl-10 pr-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                            />
                        </div>
                    </form>

                    {/* Navigation Links */}
                    <div className="hidden md:flex items-center gap-4">
                        <Link
                            href="/papers"
                            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                        >
                            Papers
                        </Link>
                        <Link
                            href="/trending"
                            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                        >
                            Trending
                        </Link>

                        {isAuthenticated ? (
                            <div className="relative group">
                                <button className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
                                    <User className="w-4 h-4" />
                                    {user?.full_name || user?.email?.split('@')[0]}
                                </button>
                                <div className="absolute right-0 mt-2 w-48 bg-card border border-border rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all">
                                    <Link href="/dashboard" className="block px-4 py-2 text-sm hover:bg-secondary">
                                        Dashboard
                                    </Link>
                                    <button onClick={logout} className="block w-full text-left px-4 py-2 text-sm hover:bg-secondary text-destructive">
                                        Logout
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <Link
                                href="/auth/login"
                                className="flex items-center gap-2 text-sm font-medium bg-primary text-primary-foreground px-4 py-2 rounded-lg hover:bg-primary/90 transition-colors"
                            >
                                <LogIn className="w-4 h-4" />
                                Sign In
                            </Link>
                        )}
                    </div>

                    {/* Mobile menu button */}
                    <button
                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                        className="md:hidden p-2"
                    >
                        {isMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                    </button>
                </div>

                {/* Mobile menu */}
                {isMenuOpen && (
                    <div className="md:hidden py-4 space-y-4">
                        <form onSubmit={handleSearch}>
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                <input
                                    type="text"
                                    placeholder="Search papers..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="w-full bg-secondary rounded-lg pl-10 pr-4 py-2 text-sm"
                                />
                            </div>
                        </form>
                        <div className="flex flex-col gap-2">
                            <Link href="/papers" className="py-2 text-sm font-medium">Papers</Link>
                            <Link href="/trending" className="py-2 text-sm font-medium">Trending</Link>
                            {isAuthenticated ? (
                                <>
                                    <Link href="/dashboard" className="py-2 text-sm font-medium">Dashboard</Link>
                                    <button onClick={logout} className="py-2 text-left text-sm font-medium text-destructive">Logout</button>
                                </>
                            ) : (
                                <Link href="/auth/login" className="py-2 text-sm font-medium">Sign In</Link>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </nav>
    );
}
