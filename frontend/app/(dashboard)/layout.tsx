import SidebarNav from "@/components/layout/SidebarNav";
import MobileHeader from "@/components/layout/MobileHeader";
import MobileBottomNav from "@/components/layout/MobileBottomNav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[#f6f5fa]">
      <SidebarNav />
      <div className="min-w-0 flex-1 md:ml-[240px] flex flex-col min-h-screen">
        <MobileHeader />
        <main id="main-content" className="flex-1 p-4 md:p-7 xl:px-9 pb-24 md:pb-8 max-w-[1440px] w-full mx-auto">
          {children}
        </main>
      </div>
      <MobileBottomNav />
    </div>
  );
}
