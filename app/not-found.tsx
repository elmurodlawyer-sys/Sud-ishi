import Link from "next/link";

export default function NotFound() {
  return (
    <div className="card empty">
      <h1>Sahifa topilmadi</h1>
      <p><Link href="/">Bosh sahifaga qaytish</Link></p>
    </div>
  );
}
