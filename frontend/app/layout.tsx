import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aurelio Coffee Co. — AI Support & Sales",
  description: "AI Support and Sales Agent for Aurelio Coffee Co.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
