import type { Metadata } from "next";
import Link from "next/link";
import Nav from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sud ishi monitoringi",
  description: "Sud ishlarini ro'yxatga olish va kuzatish tizimi",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body>
        <header className="topbar">
          <div className="container topbar-inner">
            <Link href="/" className="brand">⚖️ Sud ishi monitoringi</Link>
            <Nav />
          </div>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
