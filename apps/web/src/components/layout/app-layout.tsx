import {
  Activity,
  Archive,
  BarChart3,
  BookmarkCheck,
  Boxes,
  DatabaseZap,
  GitCompareArrows,
  Languages,
  Menu,
  MoonStar,
  Search,
  ListChecks,
  SlidersHorizontal,
  Sun,
  type LucideIcon,
} from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { loadGsap, motion } from "@/lib/motion";
import { useTheme } from "@/lib/theme";

interface NavigationItem {
  path: string;
  label: TranslationKey;
  icon: LucideIcon;
  group: "discover" | "analyze" | "library" | "operations";
}

const navigation: NavigationItem[] = [
  { path: "/search", label: "nav.search", icon: Search, group: "discover" },
  { path: "/clusters", label: "nav.clusters", icon: Boxes, group: "discover" },
  { path: "/analytics", label: "nav.analytics", icon: BarChart3, group: "analyze" },
  { path: "/compare", label: "nav.compare", icon: GitCompareArrows, group: "analyze" },
  { path: "/history", label: "nav.history", icon: Archive, group: "library" },
  { path: "/saved", label: "nav.saved", icon: ListChecks, group: "library" },
  { path: "/bookmarks", label: "nav.bookmarks", icon: BookmarkCheck, group: "library" },
  { path: "/sources", label: "nav.sources", icon: DatabaseZap, group: "operations" },
  { path: "/system", label: "nav.system", icon: Activity, group: "operations" },
  { path: "/settings", label: "nav.settings", icon: SlidersHorizontal, group: "operations" },
];

const primaryPaths = new Set(["/search", "/clusters", "/analytics", "/compare", "/history"]);
const groups = ["discover", "analyze", "library", "operations"] as const;

function MirsadMark() {
  return (
    <svg viewBox="0 0 42 42" role="img" aria-label="MIRSAD" className="mirsad-mark">
      <path d="M5 34V8l16 13L37 8v26" />
      <path d="M5 8h32M5 34h32" />
      <circle cx="21" cy="21" r="3.5" />
    </svg>
  );
}

function currentItem(pathname: string) {
  return navigation.find((item) => pathname.startsWith(item.path)) ?? navigation[0];
}

function RouteLink({ item, compact = false }: { item: NavigationItem; compact?: boolean }) {
  const { t } = useI18n();
  return (
    <NavLink
      to={item.path}
      className={({ isActive }) => `route-aperture__link${isActive ? " is-active" : ""}${compact ? " route-aperture__link--compact" : ""}`}
    >
      <item.icon className="route-aperture__icon" aria-hidden="true" />
      <span className="route-aperture__label">{t(item.label)}</span>
      <span className="route-aperture__signal" aria-hidden="true" />
    </NavLink>
  );
}

function MobileNavigation() {
  const { direction, t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger render={<Button variant="ghost" size="icon" className="mobile-navigation-trigger" data-navigation-menu="trigger" aria-label={t("action.navigationMenu")} aria-expanded={open} />}>
        <Menu />
      </SheetTrigger>
      <SheetContent
        side={direction === "rtl" ? "right" : "left"}
        dir={direction}
        data-slot="sidebar"
        data-mobile="true"
        data-navigation-menu="content"
        className="route-drawer w-[min(88vw,360px)] p-0"
      >
        <SheetHeader className="border-b px-6 py-5 text-start">
          <SheetTitle className="flex items-center gap-3"><MirsadMark /> {t("app.name")}</SheetTitle>
          <SheetDescription>{t("app.subtitle")}</SheetDescription>
        </SheetHeader>
        <nav className="navigation-groups" aria-label={t("nav.workspace")}>
          {groups.map((group) => (
            <section key={group}>
              <h2>{t(`nav.${group}`)}</h2>
              {navigation.filter((item) => item.group === group).map((item) => (
                <div key={item.path} onClick={() => setOpen(false)}>
                  <RouteLink item={item} compact />
                </div>
              ))}
            </section>
          ))}
        </nav>
      </SheetContent>
    </Sheet>
  );
}

function WorkspaceNavigation() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="desktop-navigation-trigger"
            data-navigation-menu="trigger"
            aria-label={t("action.navigationMenu")}
            aria-expanded={open}
          />
        }
      >
        <Menu />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="workspace-navigation-menu"
        data-navigation-menu="content"
      >
        {groups.map((group, index) => (
          <DropdownMenuGroup key={group}>
            {index > 0 && <DropdownMenuSeparator />}
            <DropdownMenuLabel>{t(`nav.${group}`)}</DropdownMenuLabel>
            {navigation.filter((item) => item.group === group).map((item) => (
              <DropdownMenuItem
                key={item.path}
                nativeButton={false}
                render={<NavLink to={item.path} />}
                onClick={() => setOpen(false)}
              >
                <item.icon aria-hidden="true" />
                {t(item.label)}
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function UtilityControls() {
  const { locale, setLocale, t } = useI18n();
  const { theme, setTheme } = useTheme();
  return (
    <div className="instrument-utilities">
      <Tooltip>
        <TooltipTrigger render={<span className="instrument-local-state" role="status" tabIndex={0} />}>
          <i aria-hidden="true" />
          <span>{t("app.onDevice")}</span>
        </TooltipTrigger>
        <TooltipContent>{t("app.onDeviceDescription")}</TooltipContent>
      </Tooltip>
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button variant="ghost" size="icon" aria-label={t("action.language")} />}>
          <Languages />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup><DropdownMenuLabel>{t("action.language")}</DropdownMenuLabel></DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setLocale("en")} data-active={locale === "en"}>{t("common.english")}</DropdownMenuItem>
          <DropdownMenuItem onClick={() => setLocale("ar")} data-active={locale === "ar"}>{t("common.arabic")}</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button variant="ghost" size="icon" aria-label={t("action.theme")} />}>
          {theme === "dark" ? <MoonStar /> : <Sun />}
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup><DropdownMenuLabel>{t("action.theme")}</DropdownMenuLabel></DropdownMenuGroup>
          <DropdownMenuSeparator />
          {(["light", "dark", "system"] as const).map((item) => (
            <DropdownMenuItem key={item} onClick={() => setTheme(item)} data-active={theme === item}>
              {t(`common.${item}` as TranslationKey)}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <WorkspaceNavigation />
    </div>
  );
}

export function AppLayout() {
  const { t } = useI18n();
  const location = useLocation();
  const route = currentItem(location.pathname);
  const routeStage = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let disposed = false;
    let cleanup: (() => void) | undefined;
    void loadGsap().then((gsap) => {
      if (disposed || !routeStage.current) return;
      const context = gsap.context(() => {
        const media = gsap.matchMedia();
        media.add("(prefers-reduced-motion: no-preference)", () => {
          gsap.fromTo(
            routeStage.current,
            { opacity: 0.35, y: 12, clipPath: "inset(0 0 6% 0)" },
            { opacity: 1, y: 0, clipPath: "inset(0 0 0% 0)", duration: motion.quick, ease: motion.ease },
          );
        });
        cleanup = () => media.revert();
      }, routeStage);
      const previous = cleanup;
      cleanup = () => { previous?.(); context.revert(); };
    });
    return () => { disposed = true; cleanup?.(); };
  }, [location.pathname]);

  return (
    <div className="instrument-shell" data-route={route.path.slice(1)}>
      <header
        className="instrument-command-layer"
      >
        <div className="instrument-command-layer__primary">
          <div className="instrument-brand-group">
            <MobileNavigation />
            <NavLink to="/search" className="instrument-identity" aria-label={t("app.name")}>
              <MirsadMark />
              <span className="instrument-identity__word">{t("app.name")}</span>
              <span className="instrument-identity__version">1.2</span>
            </NavLink>
          </div>
          <nav className="route-aperture" aria-label={t("nav.workspace")}>
            {navigation.filter((item) => primaryPaths.has(item.path)).map((item) => (
              <RouteLink key={item.path} item={item} />
            ))}
          </nav>
          <UtilityControls />
        </div>
      </header>
      <main className="instrument-field">
        <div ref={routeStage} className="instrument-stage">
          <Outlet />
        </div>
      </main>
      <footer className="instrument-status-line" aria-hidden="true">
        <span>{t("app.name")} / {t("app.localFirst")}</span><i /><span>{t("app.rankingArchitecture")}</span><i /><span>{t("app.maferPhase")}</span>
      </footer>
    </div>
  );
}
