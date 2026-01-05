import Link from 'next/link';
import { Navbar } from '@/components/Navbar';
import { ArrowRight, Zap, Code, Brain, TrendingUp, BookOpen, Star } from 'lucide-react';

export default function HomePage() {
    return (
        <div className="min-h-screen">
            <Navbar />

            {/* Hero Section */}
            <section className="relative overflow-hidden">
                {/* Background gradient */}
                <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-background to-background" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-transparent to-transparent" />

                <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 lg:py-32">
                    <div className="text-center">
                        {/* Badge */}
                        <div className="inline-flex items-center gap-2 bg-primary/10 border border-primary/20 rounded-full px-4 py-1.5 mb-6">
                            <Zap className="w-4 h-4 text-primary" />
                            <span className="text-sm font-medium text-primary">Free & Open Source</span>
                        </div>

                        {/* Title */}
                        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-foreground mb-6">
                            Discover Research Papers
                            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-primary to-purple-400">
                                That Actually Matter
                            </span>
                        </h1>

                        {/* Description */}
                        <p className="max-w-2xl mx-auto text-lg text-muted-foreground mb-8">
                            Paper Radar aggregates, ranks, and personalizes research papers from arXiv,
                            Semantic Scholar, and GitHub. Find trending papers, track citations,
                            and discover implementations—all in one place.
                        </p>

                        {/* CTA Buttons */}
                        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                            <Link
                                href="/papers"
                                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-primary text-primary-foreground px-8 py-3 rounded-lg font-medium hover:bg-primary/90 transition-colors"
                            >
                                Explore Papers
                                <ArrowRight className="w-4 h-4" />
                            </Link>
                            <Link
                                href="/trending"
                                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-secondary text-secondary-foreground px-8 py-3 rounded-lg font-medium hover:bg-secondary/80 transition-colors"
                            >
                                <TrendingUp className="w-4 h-4" />
                                View Trending
                            </Link>
                        </div>
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section className="py-20 bg-card/50">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="text-center mb-12">
                        <h2 className="text-3xl font-bold text-foreground mb-4">
                            Everything You Need to Stay Current
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Built for researchers, by researchers. We solve the problem of finding
                            relevant papers in the ever-growing sea of publications.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                        {/* Feature 1 */}
                        <div className="bg-background border border-border rounded-xl p-6 hover:border-primary/50 transition-colors">
                            <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4">
                                <TrendingUp className="w-6 h-6 text-primary" />
                            </div>
                            <h3 className="text-lg font-semibold text-foreground mb-2">
                                Smart Ranking
                            </h3>
                            <p className="text-muted-foreground text-sm">
                                Papers ranked by citation velocity, GitHub stars, and social buzz.
                                See what's actually gaining traction in the community.
                            </p>
                        </div>

                        {/* Feature 2 */}
                        <div className="bg-background border border-border rounded-xl p-6 hover:border-primary/50 transition-colors">
                            <div className="w-12 h-12 bg-green-500/10 rounded-lg flex items-center justify-center mb-4">
                                <Code className="w-6 h-6 text-green-500" />
                            </div>
                            <h3 className="text-lg font-semibold text-foreground mb-2">
                                Implementation Finder
                            </h3>
                            <p className="text-muted-foreground text-sm">
                                Automatically discover GitHub repos and HuggingFace models
                                that implement each paper. Skip the hunting.
                            </p>
                        </div>

                        {/* Feature 3 */}
                        <div className="bg-background border border-border rounded-xl p-6 hover:border-primary/50 transition-colors">
                            <div className="w-12 h-12 bg-blue-500/10 rounded-lg flex items-center justify-center mb-4">
                                <Brain className="w-6 h-6 text-blue-500" />
                            </div>
                            <h3 className="text-lg font-semibold text-foreground mb-2">
                                AI Summaries
                            </h3>
                            <p className="text-muted-foreground text-sm">
                                Get concise, AI-generated summaries that capture the key innovation,
                                problem, and results of each paper.
                            </p>
                        </div>
                    </div>
                </div>
            </section>

            {/* Stats Section */}
            <section className="py-16">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                        <div className="text-center">
                            <div className="text-3xl font-bold text-foreground mb-1">10k+</div>
                            <div className="text-sm text-muted-foreground">Papers Indexed</div>
                        </div>
                        <div className="text-center">
                            <div className="text-3xl font-bold text-foreground mb-1">6</div>
                            <div className="text-sm text-muted-foreground">Categories</div>
                        </div>
                        <div className="text-center">
                            <div className="text-3xl font-bold text-foreground mb-1">500+</div>
                            <div className="text-sm text-muted-foreground">Daily Updates</div>
                        </div>
                        <div className="text-center">
                            <div className="text-3xl font-bold text-foreground mb-1">100%</div>
                            <div className="text-sm text-muted-foreground">Free to Use</div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Category Cards Section */}
            <section className="py-16 bg-card/50">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <h2 className="text-2xl font-bold text-foreground mb-8 text-center">
                        Browse by Category
                    </h2>

                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                        {[
                            { id: 'cs.AI', name: 'AI', color: 'from-purple-500 to-purple-600' },
                            { id: 'cs.LG', name: 'ML', color: 'from-blue-500 to-blue-600' },
                            { id: 'cs.CV', name: 'Vision', color: 'from-green-500 to-green-600' },
                            { id: 'cs.CL', name: 'NLP', color: 'from-orange-500 to-orange-600' },
                            { id: 'cs.NE', name: 'Neural', color: 'from-pink-500 to-pink-600' },
                            { id: 'stat.ML', name: 'Stats', color: 'from-cyan-500 to-cyan-600' },
                        ].map((cat) => (
                            <Link
                                key={cat.id}
                                href={`/papers?category=${cat.id}`}
                                className={`bg-gradient-to-br ${cat.color} rounded-xl p-4 text-center text-white font-medium hover:scale-105 transition-transform`}
                            >
                                {cat.name}
                            </Link>
                        ))}
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer className="border-t border-border py-8">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center">
                                <span className="text-white font-bold text-xs">PR</span>
                            </div>
                            <span className="text-sm text-muted-foreground">Paper Radar © 2026</span>
                        </div>
                        <div className="flex items-center gap-6 text-sm text-muted-foreground">
                            <Link href="/about" className="hover:text-foreground">About</Link>
                            <Link href="/privacy" className="hover:text-foreground">Privacy</Link>
                            <a href="https://github.com" className="hover:text-foreground">GitHub</a>
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    );
}
