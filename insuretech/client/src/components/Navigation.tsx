import { SignedIn, UserButton } from "@clerk/clerk-react";
import { Shell, SquareMenu } from "lucide-react";
import { COLORS } from "../constants/colors";

interface NavigationProps {
  onMenuToggle: () => void;
  isMenuVisible: boolean;
}

export default function Navigation({ onMenuToggle, isMenuVisible }: NavigationProps) {
  return (
    <div className={`w-16 ${COLORS.navigationBackground} flex flex-col items-center py-6 gap-4 ${COLORS.panelShadow} border-r ${COLORS.panelBorder}`}>
      {/* Logo/Brand area */}
      <div className="text-gray-600 mb-4">
        <Shell size={32} strokeWidth={2} />
      </div>

      {/* Menu toggle button */}
      <button
        onClick={onMenuToggle}
        className="text-gray-600 hover:text-gray-900 hover:bg-gray-100 p-2 rounded-md transition-colors"
        title={isMenuVisible ? "Hide Menu" : "Show Menu"}
        aria-label={isMenuVisible ? "Hide Menu" : "Show Menu"}
      >
        <SquareMenu size={24} strokeWidth={2} />
      </button>

      {/* Spacer to push auth to bottom */}
      <div className="flex-1" />

      {/* Authentication section */}
      <div className="flex flex-col items-center gap-4 mb-2">
        <SignedIn>
          <UserButton
            appearance={{
              elements: {
                avatarBox: "w-10 h-10",
                userButtonTrigger: "focus:shadow-none",
                userButtonPopoverCard: "shadow-xl",
                userButtonPopoverActionButton: "text-sm py-2",
                userButtonPopoverActionButtonText: "text-sm",
                userButtonPopoverFooter: "hidden"
              }
            }}
          />
        </SignedIn>
      </div>
    </div>
  );
}
