"use client";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { NAV_ITEMS } from "@/lib/constants";
import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function MobileNavMenu() {
  const pathname = usePathname();

  const items = NAV_ITEMS.filter((item) => item.href !== "/search");

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="icon"
          variant="outline"
          className="border-gray-600 bg-transparent text-gray-200 hover:bg-white/5"
          aria-label="Open navigation menu"
        >
          <Menu className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        className="w-52 border-gray-600 bg-gray-800 text-gray-100"
      >
        {items.map((item) => {
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);

          return (
            <DropdownMenuItem
              key={item.href}
              asChild
              className={active ? "bg-white/10 text-gray-100" : ""}
            >
              <Link href={item.href}>{item.label}</Link>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
