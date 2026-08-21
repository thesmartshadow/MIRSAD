import {
  Activity,
  Archive,
  BarChart3,
  BookmarkCheck,
  Boxes,
  DatabaseZap,
  GitCompareArrows,
  Languages,
  MoonStar,
  Search,
  ListChecks,
  Settings2,
  SlidersHorizontal,
  Sun,
  type LucideIcon,
} from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
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
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";

interface NavigationGroup {
  label: TranslationKey;
  items: Array<{ path: string; label: TranslationKey; icon: LucideIcon }>;
}

const navigation: NavigationGroup[] = [
  {
    label: "nav.workspace",
    items: [
      { path: "/search", label: "nav.search", icon: Search },
      { path: "/analytics", label: "nav.analytics", icon: BarChart3 },
      { path: "/clusters", label: "nav.clusters", icon: Boxes },
      {
        path: "/compare",
        label: "nav.compare",
        icon: GitCompareArrows,
      },
      { path: "/history", label: "nav.history", icon: Archive },
      { path: "/saved", label: "nav.saved", icon: ListChecks },
      { path: "/bookmarks", label: "nav.bookmarks", icon: BookmarkCheck },
    ],
  },
  {
    label: "nav.operations",
    items: [
      { path: "/sources", label: "nav.sources", icon: DatabaseZap },
      { path: "/system", label: "nav.system", icon: Activity },
      {
        path: "/settings",
        label: "nav.settings",
        icon: SlidersHorizontal,
      },
    ],
  },
];

function ApplicationSidebar() {
  const { direction, t } = useI18n();
  const location = useLocation();
  return (
    <Sidebar
      collapsible="icon"
      variant="inset"
      side={direction === "rtl" ? "right" : "left"}
      dir={direction}
    >
      <SidebarHeader className="h-16 justify-center border-b border-sidebar-border px-3">
        <NavLink
          to="/search"
          className="flex items-center gap-2 overflow-hidden"
        >
          <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-sidebar-primary font-semibold text-sidebar-primary-foreground">
            M
          </div>
          <div className="min-w-0 group-data-[collapsible=icon]:hidden">
            <div className="font-heading text-sm font-semibold tracking-[0.12em]">
              {t("app.name")}
            </div>
            <div className="truncate text-[10px] text-muted-foreground">
              {t("app.subtitle")}
            </div>
          </div>
        </NavLink>
      </SidebarHeader>
      <SidebarContent>
        {navigation.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{t(group.label)}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => {
                  const active = location.pathname.startsWith(item.path);
                  return (
                    <SidebarMenuItem key={item.path}>
                      <SidebarMenuButton
                        render={<NavLink to={item.path} />}
                        isActive={active}
                        tooltip={t(item.label)}
                      >
                        <item.icon />
                        <span>{t(item.label)}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarSeparator />
      <SidebarFooter>
        <div className="flex items-center justify-between gap-2 px-2 group-data-[collapsible=icon]:hidden">
          <span className="text-xs text-muted-foreground">
            {t("app.local")} v1.1.0
          </span>
          <span
            className="size-2 rounded-full bg-chart-4"
            aria-label={t("app.apiConfigured")}
            role="status"
          />
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

function pageTitle(pathname: string): TranslationKey {
  const entry = navigation
    .flatMap((group) => group.items)
    .find((item) => pathname.startsWith(item.path));
  return entry?.label ?? "nav.search";
}

function Topbar() {
  const { locale, setLocale, t } = useI18n();
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background px-4 md:px-6">
      <SidebarTrigger />
      <div className="h-5 w-px bg-border" />
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-sm font-semibold">
          {t(pageTitle(location.pathname))}
        </h1>
      </div>
      <Badge variant="outline" className="hidden gap-1.5 font-normal sm:flex">
        <span className="size-1.5 rounded-full bg-chart-4" /> {t("app.local")}
      </Badge>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("action.language")}
            />
          }
        >
          <Languages />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            <DropdownMenuLabel>{t("action.language")}</DropdownMenuLabel>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => setLocale("en")}
            data-active={locale === "en"}
          >
            {t("common.english")}
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => setLocale("ar")}
            data-active={locale === "ar"}
          >
            {t("common.arabic")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("action.theme")}
            />
          }
        >
          {theme === "dark" ? <MoonStar /> : <Sun />}
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            <DropdownMenuLabel>{t("action.theme")}</DropdownMenuLabel>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          {(["light", "dark", "system"] as const).map((item) => (
            <DropdownMenuItem
              key={item}
              onClick={() => setTheme(item)}
              data-active={theme === item}
            >
              {t(`common.${item}` as TranslationKey)}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <Button
        nativeButton={false}
        variant="ghost"
        size="icon"
        render={<NavLink to="/settings" aria-label={t("nav.settings")} />}
      >
        <Settings2 />
      </Button>
    </header>
  );
}

export function AppLayout() {
  return (
    <SidebarProvider>
      <ApplicationSidebar />
      <SidebarInset className="min-w-0">
        <Topbar />
        <div className="mx-auto w-full max-w-[1600px] flex-1 p-4 md:p-6">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
