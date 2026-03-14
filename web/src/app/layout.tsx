import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WWSC Twitter Bot",
  description: "Multi-user Discord to Twitter auto-poster management portal",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-gray-950 text-white min-h-screen font-sans">
        {children}
      </body>
    </html>
  );
}
