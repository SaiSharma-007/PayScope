import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowRight, Pencil, Check, MessageSquare, Moon, Play } from 'lucide-react'
import { useAuth } from '../auth/useAuth'
import Brand from '@/components/Brand'
import ThemeSwitch from '@/components/ThemeSwitch'
import { Bubble, BubbleContent } from '@/components/ui/bubble'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card'
import { Message, MessageContent } from '@/components/ui/message'
import {
  MessageScroller, MessageScrollerContent, MessageScrollerItem,
  MessageScrollerProvider, MessageScrollerViewport,
} from '@/components/ui/message-scroller'
import {
  NavigationMenu, NavigationMenuItem, NavigationMenuLink, NavigationMenuList,
} from '@/components/ui/navigation-menu'
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  Trace, TraceCollapsible, TraceCollapsibleContent, TraceCollapsibleTrigger,
  TraceIcon, TraceLine, TraceTitle,
} from '@/components/ui/trace'
import './landing.css'

const scope = 'Engineering · India · INR'
const question = 'What is the median annual base pay for Engineering in India?'
const figures = [
  { label: 'Minimum', amount: 840000 },
  { label: 'Median', amount: 1680000 },
  { label: 'Maximum', amount: 2900000 },
]
const median = figures[1]
const PayRange = lazy(() => import('./PayRange.jsx'))

function EmployeeExample() {
  const [saved, setSaved] = useState(false)
  const [pointer, setPointer] = useState(false)
  const [highlight, setHighlight] = useState(false)
  return (
    <Card className="landing-offer-specimen">
      <CardHeader><h4>Employee directory</h4><CardDescription>India · Engineering · Illustrative data</CardDescription></CardHeader>
      <CardContent>
        <Sheet>
          <Table className="landing-offer-table">
            <TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Annual base pay</TableHead></TableRow></TableHeader>
            <TableBody><TableRow data-highlight={highlight} onAnimationEnd={() => setHighlight(false)}>
              <th scope="row">Asha Rao</th><TableCell>{formatPay(saved ? 1620000 : 1560000)}</TableCell>
            </TableRow></TableBody>
          </Table>
          <SheetTrigger asChild>
            <Button variant="outline" data-salary-review="" onClick={event => setPointer(event.detail > 0)}>
              <Pencil data-icon="inline-start" />
              Review salary update
            </Button>
          </SheetTrigger>
          <SheetContent className="landing-demo-sheet" data-motion={pointer} onKeyDown={() => setPointer(false)}>
            <SheetHeader><SheetTitle>Review Asha’s salary</SheetTitle><SheetDescription>Illustrative update · Annual base pay</SheetDescription></SheetHeader>
            <div className="landing-sheet-values">
              <p>Current pay <strong>{formatPay(saved ? 1620000 : 1560000)}</strong></p>
              <p>Proposed pay <strong>{formatPay(1620000)}</strong></p>
              <SheetClose asChild><Button onClick={event => { setHighlight(event.detail > 0 && !saved); setSaved(true) }} disabled={saved}>Save example update</Button></SheetClose>
            </div>
          </SheetContent>
        </Sheet>
        <p role="status">{saved && 'Example update saved.'}</p>
      </CardContent>
    </Card>
  )
}

function CompensationExample() {
  const [pointer, setPointer] = useState(false)
  return (
    <Card className="landing-offer-specimen">
      <CardHeader><h4>Package preview</h4><CardDescription>Illustrative data · INR per year</CardDescription></CardHeader>
      <CardContent>
        <Tabs defaultValue="guaranteed" onPointerDown={() => setPointer(true)} onKeyDown={() => setPointer(false)}>
          <TabsList aria-label="Compensation basis">
            <TabsTrigger value="guaranteed">Guaranteed</TabsTrigger>
            <TabsTrigger value="target">Including target</TabsTrigger>
          </TabsList>
          <TabsContent value="guaranteed" data-fade={pointer}><p className="landing-demo-total">{formatPay(1620000)}</p><p>Annual base pay</p></TabsContent>
          <TabsContent value="target" data-fade={pointer}><p className="landing-demo-total">{formatPay(1782000)}</p><p>Annual base pay plus a 10% target bonus of {formatPay(162000)}</p></TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

function RangeAnswerExample() {
  const [open, setOpen] = useState(false)
  const [animate, setAnimate] = useState(false)
  return (
    <Card className="landing-offer-specimen">
      <CardHeader><h4>How wide is Engineering’s pay range in India?</h4><CardDescription>Illustrative answer · INR</CardDescription></CardHeader>
      <CardContent>
        <p className="landing-demo-total">{formatPay(figures[2].amount - figures[0].amount)}</p>
        <div className="landing-brief-trace" data-reveal={animate}>
          <EvidenceTrace open={open} setOpen={setOpen} setAnimate={setAnimate} steps={[
            'Filter to Engineering employees in India with annual base pay recorded in INR.',
            'Subtract ₹8,40,000 from ₹29,00,000.',
          ]}>
            <Button asChild variant="link"><a href="#insights-example">View figures <ArrowRight data-icon="inline-end" /></a></Button>
          </EvidenceTrace>
        </div>
      </CardContent>
    </Card>
  )
}

const offerings = [
  { title: 'Find one employee and update their pay.', description: 'Filter the directory to Engineering in India, then review a proposed update to Asha Rao’s annual base pay.', Example: EmployeeExample },
  { title: 'See what changes before you publish.', description: 'Review a package with ₹16,20,000 in base pay and a 10% target bonus. Switch between the guaranteed amount and the total including target.', Example: CompensationExample },
  { title: 'See where Engineering pay lands.', description: 'Compare annual base pay within one currency. Match the median marker to the exact figure in the table.', Example: () => <PayReport embedded /> },
  { title: 'Check the report behind the answer.', description: 'Ask a follow-up about the same group. Expand the report activity to check the filters and arithmetic, then open the figures used in the answer.', Example: RangeAnswerExample },
]

function LandingOfferings() {
  const section = useRef(null)

  useEffect(() => {
    if (!window.IntersectionObserver) return
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        entry.target.setAttribute('data-arrived', '')
        observer.unobserve(entry.target)
      }
    }, { threshold: 0.2 })
    section.current.querySelectorAll('.landing-offer').forEach(row => observer.observe(row))
    return () => observer.disconnect()
  }, [])

  return (
    <section ref={section} className="landing-offerings landing-width" id="offerings" aria-labelledby="offerings-title">
      <Separator />
      <h2 id="offerings-title" tabIndex={-1}>What PayScope offers</h2>
      {offerings.map(({ title, description, Example }) => (
        <article className="landing-offer" key={title}>
          <div className="landing-offer-copy"><h3>{title}</h3><p>{description}</p></div>
          <Example />
        </article>
      ))}
    </section>
  )
}

const formatPay = new Intl.NumberFormat('en-IN', {
  style: 'currency', currency: 'INR', maximumFractionDigits: 0,
}).format

function PayReport({ animate, embedded = false }) {
  return (
    <Card tabIndex={embedded ? -1 : undefined} className={embedded ? "landing-offer-specimen" : "landing-surface landing-report"} id={embedded ? "insights-example" : "example-report"}>
      <CardHeader>
        <h2>Annual base pay</h2>
        <CardDescription>{scope} · Illustrative data</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="landing-range" aria-hidden="true" data-reveal={animate}>
          <Suspense fallback={null}>
            <PayRange figures={figures} />
          </Suspense>
        </div>
        <Table className="landing-figures">
          <TableCaption className="sr-only">Exact annual base pay figures in INR</TableCaption>
          <TableHeader className="sr-only">
            <TableRow><TableHead>Measure</TableHead><TableHead>Annual base pay</TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {figures.map(({ label, amount }) => (
              <TableRow key={label} data-median={label === median.label}>
                <th scope="row">{label}</th>
                <TableCell>{formatPay(amount)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function EvidenceTrace({ open, setOpen, setAnimate, children, steps = [
  "Apply the Engineering and India filters in INR.",
  "Calculate the median for the illustrative group.",
  "Check it against the report’s exact figures.",
] }) {
  const [pointer, setPointer] = useState(false)
  return (
    <Trace>
      <TraceCollapsible open={open} onOpenChange={(next) => {
        setOpen(next)
        if (!next) setAnimate(false)
      }}>
        <TraceCollapsibleTrigger onClick={event => {
          setPointer(event.detail > 0)
          setAnimate(!open && event.detail > 0)
        }}>
          How the answer was checked
        </TraceCollapsibleTrigger>
        <TraceCollapsibleContent data-motion={pointer}>
          {steps.map(step => (
            <TraceLine key={step}>
              <TraceIcon><Check /></TraceIcon>
              <TraceTitle>{step}</TraceTitle>
            </TraceLine>
          ))}
          {children}
        </TraceCollapsibleContent>
      </TraceCollapsible>
    </Trace>
  )
}

function LandingHeader({ signedIn, destination }) {
  return (
    <header className="landing-header landing-width">
      <Brand />
      <NavigationMenu viewport={false} aria-label="Main navigation">
        <NavigationMenuList>
          <NavigationMenuItem className="landing-example-link">
            <NavigationMenuLink asChild>
              <a href="#example"><Play size={16} aria-hidden="true" />Try the example</a>
            </NavigationMenuLink>
          </NavigationMenuItem>
          <NavigationMenuItem>
            <label className="landing-mode">
              <Moon size={15} aria-hidden="true" />
              <span>Dark theme</span>
              <ThemeSwitch compact />
            </label>
          </NavigationMenuItem>
          <NavigationMenuItem>
            <Button variant="ghost" size="sm" asChild><Link to={destination}>{signedIn ? 'Workspace' : 'Sign in'}</Link></Button>
          </NavigationMenuItem>
        </NavigationMenuList>
      </NavigationMenu>
    </header>
  )
}

export default function Landing() {
  const auth = useAuth()
  const [traceOpen, setTraceOpen] = useState(false)
  const [animate, setAnimate] = useState(false)
  const destination = auth.session ? '/employees' : '/sign-in'

  return (
    <div className="payscope-landing">
      <LandingHeader destination={destination} signedIn={Boolean(auth.session)} />
      <main id="main">
        <section className="landing-stage landing-width" aria-labelledby="landing-heading">
          <div className="landing-intro" data-enter>
            <h1 id="landing-heading">Every pay answer should show its numbers.</h1>
            <p>Maintain salary records, compare pay within a currency, and check the figures behind each answer.</p>
            <Button asChild size="lg" data-workspace-action="">
              <Link to={destination}>Open HR workspace <ArrowRight data-icon="inline-end" /></Link>
            </Button>
            <Button asChild variant="link" size="lg">
              <a href="#offerings">Explore features <ArrowDown data-icon="inline-end" /></a>
            </Button>
          </div>

          <MessageScrollerProvider autoScroll={false}>
            <MessageScroller className="landing-question" id="example" tabIndex={-1} aria-label="Illustrative pay question">
              <MessageScrollerViewport>
                <MessageScrollerContent>
                  <MessageScrollerItem messageId="example-question">
                    <Message>
                      <MessageContent>
                        <Bubble variant="ghost" className="landing-surface">
                          <BubbleContent>
                            <span className="landing-stage-label">Question</span>
                            <div className="landing-question-copy">
                              <MessageSquare aria-hidden="true" />
                              <p>{question}</p>
                            </div>
                          </BubbleContent>
                        </Bubble>
                      </MessageContent>
                    </Message>
                  </MessageScrollerItem>
                </MessageScrollerContent>
              </MessageScrollerViewport>
            </MessageScroller>
          </MessageScrollerProvider>

          <div className="landing-connector landing-connector-first" aria-hidden="true" />
          <Card className="landing-surface landing-answer">
            <CardHeader><h2 className="landing-stage-label">Answer</h2></CardHeader>
            <CardContent>
              <p className="landing-amount">{formatPay(median.amount)}</p>
              <p className="landing-answer-caption">Median annual base pay</p>
              <EvidenceTrace open={traceOpen} setOpen={setTraceOpen} setAnimate={setAnimate} />
            </CardContent>
          </Card>
          <div className="landing-connector landing-connector-second" data-reveal={animate} aria-hidden="true" />
          <PayReport animate={animate} />
        </section>

        <LandingOfferings />
        <section className="landing-workflow landing-width" id="overview" aria-labelledby="landing-workflow-title">
          <Separator />
          <h2 id="landing-workflow-title">Try the workflow with fictional data.</h2>
          <ol>
            <li><h3>Find an employee</h3><p>Search by name or ID, or filter by country, department and role.</p></li>
            <li><h3>Update their salary</h3><p>Record annual base pay in the employee’s currency.</p></li>
            <li><h3>Verify the change</h3><p>Open Salary Insights to check the figures against the report.</p></li>
          </ol>
          <Button asChild size="lg" data-workspace-action="">
            <Link to={destination}>Open HR workspace <ArrowRight data-icon="inline-end" /></Link>
          </Button>
        </section>
      </main>
      <footer className="landing-footer landing-width">
        <Separator />
        <p>PayScope · Assessment demo. All employee data is fictional.</p>
      </footer>
    </div>
  )
}
