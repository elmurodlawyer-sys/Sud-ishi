"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Boshqaruv paneli" },
  { href: "/ishlar", label: "Ishlar" },
  { href: "/majlislar", label: "Sud majlislari" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="nav">
      {LINKS.map((l) => {
        const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
        return (
          <Link key={l.href} href={l.href} className={active ? "active" : undefined}>
            {l.label}
          </Link>
        );
      })}
      <Link href="/ishlar/yangi" className="btn primary small">+ Yangi ish</Link>
    </nav>
  );
}
