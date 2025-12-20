import Link from "next/link";
import Image from "next/image";
import NavItems from "@/components/NavItems";
import UserDropdown from "@/components/UserDropdown";
import { searchStocks } from "@/lib/actions/finnhub.actions";
import SearchCommand from "@/components/SearchCommand";

const Header = async () => {
  const initialStocks = await searchStocks();

  return (
    <header className="sticky top-0 header">
      <div className="container header-wrapper">
        <Link href="/" className="flex items-center gap-2">
          <Image
            src="/assets/images/logo.png"
            alt="Sentrix logo"
            width={140}
            height={52}
            className="h-12 w-auto cursor-pointer"
          />
          <p className="text-white font-bold text-3xl">Sentrix</p>
        </Link>

        <div className="flex-1 flex justify-center">
          <SearchCommand
            renderAs="text"
            label="Search"
            initialStocks={initialStocks}
          />
        </div>

        <nav className="hidden sm:block">
          <NavItems initialStocks={initialStocks} />
        </nav>
      </div>
    </header>
  );
};
export default Header;
