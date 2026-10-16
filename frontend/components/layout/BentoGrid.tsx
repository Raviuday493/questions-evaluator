import React from "react";

export function BentoGrid({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`grid grid-cols-1 md:grid-cols-12 gap-6 ${className}`}>
      {children}
    </div>
  );
}

export function BentoCard({
  children,
  colSpan = 12,
  className = "",
}: {
  children: React.ReactNode;
  colSpan?: number;
  className?: string;
}) {
  const colSpanClasses: Record<number, string> = {
    4: "md:col-span-4",
    6: "md:col-span-6",
    8: "md:col-span-8",
    12: "md:col-span-12",
  };

  const spanClass = colSpanClasses[colSpan] || "md:col-span-12";

  return (
    <div className={`${spanClass} qpi-card p-6 flex flex-col justify-between ${className}`}>
      {children}
    </div>
  );
}
