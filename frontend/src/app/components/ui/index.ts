// shadcn/ui 컴포넌트 배럴 파일
// 새로운 서비스 페이지용 글래스모피즘 스타일 컴포넌트

export { Button, buttonVariants } from './button';
export type { ButtonProps } from './button';

export { Input } from './input';
export type { InputProps } from './input';

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from './dialog';

export { ScrollArea, ScrollBar } from './scroll-area';

export { Separator } from './separator';

export {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from './tooltip';

export { Avatar, AvatarImage, AvatarFallback } from './avatar';

// 기존 src/components/ui/card.tsx에서 재export
export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
