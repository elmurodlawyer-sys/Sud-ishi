"use client";

export default function ConfirmButton({
  message, children, className = "btn danger",
}: { message: string; children: React.ReactNode; className?: string }) {
  return (
    <button
      type="submit"
      className={className}
      onClick={(ev) => {
        if (!confirm(message)) ev.preventDefault();
      }}
    >
      {children}
    </button>
  );
}
