import MobileNavMenu from "@/components/MobileNavMenu";
import NavItems from "@/components/NavItems";
import SearchCommand from "@/components/SearchCommand";
import { searchStocks } from "@/lib/actions/finnhub.actions";
import Image from "next/image";
import Link from "next/link";

const Header = async () => {
  const initialStocks = await searchStocks();

  return (
    <header className="sticky top-0 header">
      <div className="container py-3">
        <div className="flex items-center gap-2 md:hidden">
          <Link href="/" className="flex items-center gap-2 shrink-0">
            <Image
              src="/assets/images/logo.png"
              alt="Sentrix logo"
              width={140}
              height={52}
              className="h-9 w-auto cursor-pointer"
            />
          </Link>

          <div className="flex-1">
            <SearchCommand
              renderAs="text"
              initialStocks={initialStocks}
              compact
            />
          </div>

          <MobileNavMenu />
        </div>

        <div className="hidden md:flex md:items-center md:justify-between md:gap-6">
          <Link href="/" className="flex items-center gap-2 shrink-0">
            <Image
              src="/assets/images/logo.png"
              alt="Sentrix logo"
              width={140}
              height={52}
              className="h-10 lg:h-12 w-auto cursor-pointer"
            />
            <p className="text-white font-bold text-2xl lg:text-3xl">Sentrix</p>
          </Link>

          <div className="flex-1 max-w-xl">
            <SearchCommand renderAs="text" initialStocks={initialStocks} />
          </div>

          <nav className="w-auto">
            <NavItems />
          </nav>
        </div>
      </div>
    </header>
  );
};
export default Header;
