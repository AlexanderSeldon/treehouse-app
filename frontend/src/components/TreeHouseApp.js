import React, { useState } from 'react';
import { 
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuList
} from "@/components/ui/navigation-menu";
import { Button } from "@/components/ui/button";
import { 
  Home, 
  User, 
  ShoppingCart, 
  MapPin, 
  Clock,
  LogOut,
  CheckCircle,
  Shield
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger
} from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardFooter, 
  CardHeader, 
  CardTitle 
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import Link from "next/link";

const TreeHouseApp = () => {
  // State for user phone number input
  const [phoneNumber, setPhoneNumber] = useState('');
  
  // Mock data for a user that would come from auth
  const user = {
    email: "demo@treehouse.com",
    role: "student"
  };
  
  // Sample logout function
  const logout = () => {
    console.log('User logged out');
  };
  
  return (
    <div className="min-h-screen bg-white text-[#1D1D1F]">
      {/* Header/Navigation */}
      <header className="border-b fixed w-full top-0 bg-white shadow-sm z-50">
        <div className="container mx-auto px-4">
          <NavigationMenu className="py-2">
            <NavigationMenuList className="w-full flex justify-between items-center">
              <NavigationMenuItem className="flex items-center">
                <Link href="/" className="flex items-center">
                  <svg 
                    xmlns="http://www.w3.org/2000/svg" 
                    viewBox="0 0 500 400" 
                    className="h-12 w-12 mr-2"
                  >
                    <g>
                      <path d="M250 60 L460 230 L460 350 L40 350 L40 230 Z" fill="#1B4332" />
                      <rect x="380" y="120" width="40" height="110" fill="#1B4332" />
                      <path 
                        d="M250 320 C340 230, 330 180, 260 200 C190 220, 140 270, 160 300 C180 330, 230 340, 250 320" 
                        fill="#FFFFFF" 
                      />
                    </g>
                  </svg>
                  <span className="text-xl font-bold">TreeHouse</span>
                </Link>
              </NavigationMenuItem>
              
              <div className="flex items-center gap-4">
                <NavigationMenuItem>
                  <Link href="/">
                    <Button variant="ghost" size="sm">
                      <Home className="h-4 w-4 mr-2" />
                      Home
                    </Button>
                  </Link>
                </NavigationMenuItem>
                
                <NavigationMenuItem>
                  <Link href="#how-it-works">
                    <Button variant="default" size="sm" className="bg-[#1B4332] hover:bg-[#2D6A4F]">
                      How It Works
                    </Button>
                  </Link>
                </NavigationMenuItem>
                
                {user && (
                  <>
                    <NavigationMenuItem>
                      <Sheet>
                        <SheetTrigger asChild>
                          <Button variant="outline" size="sm" className="relative">
                            <ShoppingCart className="h-4 w-4 mr-2" />
                            Cart
                            <span className="absolute -top-2 -right-2 bg-[#1B4332] text-white rounded-full w-5 h-5 text-xs flex items-center justify-center">
                              2
                            </span>
                          </Button>
                        </SheetTrigger>
                        <SheetContent>
                          <SheetHeader>
                            <SheetTitle>Your Cart</SheetTitle>
                            <SheetDescription>
                              Review your items before checkout
                            </SheetDescription>
                          </SheetHeader>
                          <ScrollArea className="h-[calc(100vh-200px)] my-4">
                            <div className="space-y-4">
                              <div className="flex justify-between items-start">
                                <div className="space-y-2">
                                  <h4 className="font-medium">Chipotle Burrito Bowl</h4>
                                  <div className="space-y-1">
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                      <MapPin className="h-4 w-4" />
                                      Building West Hall, Room 304
                                    </div>
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                      <Clock className="h-4 w-4" />
                                      10 minutes wait time
                                    </div>
                                  </div>
                                  <p className="text-sm text-muted-foreground">
                                    Quantity: 1
                                  </p>
                                  <p className="text-sm font-medium">
                                    $12.95
                                  </p>
                                </div>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                >
                                  Remove
                                </Button>
                              </div>
                              
                              <div className="flex justify-between items-start">
                                <div className="space-y-2">
                                  <h4 className="font-medium">Starbucks Iced Coffee</h4>
                                  <div className="space-y-1">
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                      <MapPin className="h-4 w-4" />
                                      Building East Hall, Room 112
                                    </div>
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                      <Clock className="h-4 w-4" />
                                      5 minutes wait time
                                    </div>
                                  </div>
                                  <p className="text-sm text-muted-foreground">
                                    Quantity: 1
                                  </p>
                                  <p className="text-sm font-medium">
                                    $4.95
                                  </p>
                                </div>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                >
                                  Remove
                                </Button>
                              </div>
                            </div>
                          </ScrollArea>
                          <Separator />
                          <div className="space-y-4 pt-4">
                            <div className="flex justify-between">
                              <span className="font-medium">Total</span>
                              <span className="font-bold">$17.90</span>
                            </div>
                            <Button
                              className="w-full bg-[#1B4332] hover:bg-[#2D6A4F]"
                            >
                              Proceed to Checkout
                            </Button>
                          </div>
                        </SheetContent>
                      </Sheet>
                    </NavigationMenuItem>
                    
                    <NavigationMenuItem>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4" />
                        <span className="text-sm font-medium">
                          {user.email} ({user.role})
                        </span>
                      </div>
                    </NavigationMenuItem>
                    
                    <NavigationMenuItem>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={logout}
                      >
                        <LogOut className="h-4 w-4 mr-2" />
                        Logout
                      </Button>
                    </NavigationMenuItem>
                  </>
                )}
              </div>
            </NavigationMenuList>
          </NavigationMenu>
        </div>
      </header>

      {/* Hero Section */}
      <section id="hero" className="pt-24 min-h-screen flex items-center">
        <div className="container mx-auto px-4 grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="max-w-xl">
            <div className="inline-flex items-center bg-[#1B4332] text-white font-bold px-4 py-2 rounded-lg mb-5">
              <CheckCircle className="h-5 w-5 mr-2" />
              FIRST-TIME ORDERS: PAY AFTER YOU GET YOUR FOOD!
            </div>
            
            <h1 className="text-4xl font-bold mb-2">Restaurant Delivery for ONLY $2-3</h1>
            <h2 className="text-2xl mb-4">No hidden fees, ever.</h2>
            
            <p className="mb-3">Enter your phone number once to sign up AND order - everything happens by text!</p>
            <p className="mb-3 font-bold">Pickup from a dorm host on your floor or a neighboring floor.</p>
            <p className="mb-3">Order <span className="font-bold">exactly at the 25-30 minute mark</span> of each hour to get your food at the top of the next hour. We deliver daily from 11am to 10pm.</p>
            <p className="mb-5"><span className="font-bold">Example:</span> Order at 5:25pm, pickup your food from your dorm host at 6:00pm.</p>
            
            <div className="flex flex-col sm:flex-row gap-2 mt-4">
              <Input 
                type="tel" 
                placeholder="Enter your phone # to sign up & order via text"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                className="flex-1"
              />
              <Button className="bg-[#1B4332] hover:bg-[#2D6A4F]">
                Sign Up & Get Food Alerts
              </Button>
            </div>
          </div>
          
          <div className="flex justify-center">
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              viewBox="0 0 500 400" 
              className="w-full max-w-md rounded-lg shadow-lg"
            >
              <g>
                <path d="M250 60 L460 230 L460 350 L40 350 L40 230 Z" fill="#1B4332" />
                <rect x="380" y="120" width="40" height="110" fill="#1B4332" />
                <path 
                  d="M250 320 C340 230, 330 180, 260 200 C190 220, 140 270, 160 300 C180 330, 230 340, 250 320" 
                  fill="#FFFFFF" 
                />
              </g>
            </svg>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-16 bg-[#F5F5F7]">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold text-center mb-8">How TreeHouse Works</h2>
          
          <Card className="bg-white shadow-md">
            <CardContent className="p-8">
              <div className="space-y-8 text-center">
                <div>
                  <h3 className="text-xl font-bold text-[#1B4332] mb-2">1. Pay just $2-3 for delivery</h3>
                  <p>No service fees. No markups. No subscriptions. Restaurant prices are exactly the same as in-store.</p>
                </div>
                
                <div>
                  <h3 className="text-xl font-bold text-[#1B4332] mb-2">2. Everything happens by text</h3>
                  <p>Get text alerts about upcoming deliveries, order via text, and get notifications when your food arrives.</p>
                </div>
                
                <div>
                  <h3 className="text-xl font-bold text-[#1B4332] mb-2">3. Pick up from a host in your dorm</h3>
                  <p>A TreeHouse host in your building will have your food. All orders are sealed by the restaurant before delivery.</p>
                </div>
                
                <div>
                  <h3 className="text-xl font-bold text-[#1B4332]">First time ordering? You don't pay until we hand you your food!</h3>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* How Deliveries Work Section */}
      <section id="active-batches" className="py-16 bg-[#F5F5F7]">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold text-center mb-8">How Deliveries Work</h2>
          
          <Card className="bg-[#1B4332] text-white mb-6">
            <CardContent className="p-6 text-center">
              <h3 className="text-xl font-bold mb-4">Delivery Schedule</h3>
              <p className="text-lg mb-4">We deliver every hour, on the hour, from 11am to 10pm daily</p>
              <p><strong>Important:</strong> Order between XX:20 and XX:35 of each hour (5-minute grace period)</p>
              <p>For example: Order between 1:20-1:35pm for the 2:00pm delivery batch</p>
            </CardContent>
          </Card>
          
          <Card className="mb-6">
            <CardContent className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold">Convenient Dorm Pickup</h3>
                <div className="flex items-center">
                  <Home className="h-5 w-5 mr-2" />
                  Right in your building
                </div>
              </div>
              
              <p className="mb-6">Your TreeHouse host is a fellow student living on your floor or a neighboring floor. They'll receive the food from our drivers and text you when it's ready for pickup.</p>
              
              <div className="flex justify-between items-center mb-6">
                <div className="font-bold">Delivery fee: $2-3</div>
                <div className="flex items-center text-[#1B4332]">
                  <CheckCircle className="h-5 w-5 mr-2" />
                  No other fees
                </div>
              </div>
              
              <Button className="w-full bg-[#1B4332] hover:bg-[#2D6A4F]">
                Sign up to start ordering
              </Button>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center">
                <Shield className="h-7 w-7 text-[#1B4332] mr-4" />
                <p><strong>Food Safety Guarantee:</strong> All orders are sealed with tamper-evident packaging before delivery to your dorm host.</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#1D1D1F] text-white py-12">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <h3 className="text-xl font-bold mb-4">TreeHouse</h3>
              <p>Restaurant delivery for college students<br />Just $2-3. No hidden fees, ever.</p>
            </div>
            
            <div>
              <h3 className="text-xl font-bold mb-4">Questions? Contact Us</h3>
              <p className="flex items-center mb-2">
                <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
                Call or Text: (708) 901-1754
              </p>
              <p className="flex items-center">
                <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Email: support@treehouse.com
              </p>
            </div>
          </div>
          
          <div className="border-t border-gray-700 mt-8 pt-8 text-center text-sm">
            <p>&copy; 2025 TreeHouse. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default TreeHouseApp;
