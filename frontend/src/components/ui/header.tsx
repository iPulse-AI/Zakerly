import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Navigation } from './navigation';
import { Button } from './button';
import { Input } from './input';
import { Search, Settings, User } from 'lucide-react';
import zakerlyLogo from '@/assets/zakerly-logo.png';

export function Header() {
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-sm">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo and Brand */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
          <img 
            src={zakerlyLogo} 
            alt="Zakerly" 
            className="w-8 h-8"
          />
          <h1 className="text-xl font-bold text-gradient-primary">
            Zakerly
          </h1>
        </div>

        {/* Navigation */}
        <div className="hidden lg:flex">
          <Navigation />
        </div>

        {/* Search and Actions */}
        <div className="flex items-center gap-3">
          <div className="relative hidden md:block">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search books..."
              className="pl-10 w-64"
            />
          </div>
          
          <Button variant="ghost" size="icon" className="hidden md:flex">
            <Settings className="w-4 h-4" />
          </Button>
          
          <Button variant="ghost" size="icon">
            <User className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}