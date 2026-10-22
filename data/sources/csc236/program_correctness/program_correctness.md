# Program Correctness

Source: David Liu, *Introduction to the Theory of Computation: Lecture Notes and Exercises for CSC236*, with UTM edits by Daniel Zingaro.

In our study of algorithms so far, we have mainly been concerned with their worst-case running time. While this is an important consideration of any program, there is arguably a much larger one: program correctness! That is, while it is important for our algorithms to run quickly, it is more important that they work! You are used to testing your programs to demonstrate their correctness, but your confidence depends on the quality of your testing.

In this chapter, we'll discuss methods of formally proving program correctness, without writing any tests at all. We cannot overstate the importance of this technique: a test suite cannot possibly test a program on all possible inputs (unless it is a very restricted program), and so a proof is the only way we can ensure that our programs are actually correct on all inputs. Even for larger software systems, which are far too complex to formally prove their correctness, the skills you will learn in this chapter will enable you to reason more effectively about your code; essentially, what we will teach you is the art of semantically tracing through code.

#### What is Correctness?

You may be familiar with the most common tools used to specify program correctness: preconditions and postconditions. Formally, a precondition of a function is a property that an input to the function must satisfy in order to guarantee that the function will work properly. A postcondition of a function is a property that must be satisfied after the function completes. Most commonly, this refers to properties of a return value, though it can also refer to changes to the variables passed in as with the implementation of quicksort from the previous chapter (which didn't return anything but instead changed the input list A).

Frankly, developing high-quality tests takes a huge amount of time – much longer than you probably spent on it in CSC148!

By “semantically” we mean your ability to derive meaning from code, i.e., identify exactly what the program does. This contrasts with program syntax, things like punctuation and (in Python) indentation.

##### precondition/postcondition

As a program designer, it is up to you to specify preconditions. This often balances the desire of flexibility (allowing a broad range of inputs/usages) with feasibility (how much code you want or are able to write).

A single function can have several pre-and postconditions.

Example. Consider the following code for calculating the greatest common divisor of two natural numbers. Its pre- and postconditions are shown.

```python
def gcd_rec(a, b):
    '''
    Pre: a and b are positive integers, and a >= b
    Post: returns the greatest common divisor of a and b
    '''
    if a == 1 or b == 1:
        return 1
    else if a mod b == 0:
        return b
    else:
        return gcd_rec(b, a mod b)
```

So preconditions tell us what must be true before the program starts, and postconditions tell us what must be true after the program terminates (assuming it ends at all). We have the following formal statement of correctness. Though it is written in more formal language, note that it really captures what we mean when we say that a program is "correct."

Definition (Program Correctness). Let f be a function with a set of preconditions and postconditions. Then f is correct (with respect to the pre- and postconditions) if the following holds:

For every input I to f, if I satisfies the preconditions, then  $ f(I) $ terminates, and all the postconditions hold after it terminates.

### Correctness of Recursive Programs

Consider the code for gcd_rec shown in the previous example. Here is its statement of correctness:

For all $a,b \in \mathbb{Z}^{+}$ such that $a \geq b$, $\gcd_{\mathrm{rec}}(a, b)$ terminates and returns $\gcd(a, b)$.

We'll use $\mod$ rather than % in our code, for clarity.

How do we prove that gcd_rec is correct? It should come as no surprise that we use induction, since you know by now that induction and recursion are closely related concepts. At this point in the course, you should be extremely comfortable with the following informal reasoning: "If a and b are 'small' then we can prove directly using the base case of gcd_rec that it is correct. Otherwise, the recursive call happens on 'smaller' inputs, and by induction, the recursive call is correct, and hence because of some {math, logic, etc.}, the program also returns the correct value."

Writing full induction proofs that formalise the above logic is tedious, so instead we use the fundamental idea in a looser template. For each program path from the first line to a return statement, we show that it terminates and that, when it does, the postconditions are satisfied. We do this as follows:

- If the path contains no recursive calls or loops, analyse the code line by line until the return statement.

For each recursive call on the path (if there are any), argue why the preconditions are satisfied at the time of the recursive call, and that the recursive call occurs on a “smaller” input than the original call. Then you may assume that the postconditions for the recursive call are satisfied when the recursive call terminates.

Finally, argue from the last recursive call to the end of the function why the postconditions of the original function call will hold.

For each loop, use a "loop invariant." We will deal with this in the next section.

We have described the content of an induction proof; by focusing on tracing values in the code, we are isolating the most important thinking involved. But recall that the core of induction is proving a predicate for all natural numbers; thus the final ingredient we need to account for is associating each input with a natural number: its "size." Usually, this will be very simple: the length of a list, or the value of an input number. Let us illustrate this technique using gcd_rec as our example.

Example. We will show that gcd_rec is correct. There are three program paths (this is easy to see, because of the if statements). Let's look at each one separately.

- Path 1: the program terminates at line 7. If the program goes into this block, then a = 1 or b = 1. But in these cases,  $ \gcd(a,b) = 1 $.

There is some ambiguity around what is meant by “smaller.” We will discuss this shortly.

So in essence, our "predicate" would be "for all inputs I of size n that satisfy the precondition of f, f is correct on I."

because  $ \gcd(x,1)=1 $ for all x. Then the postcondition holds, since at line 7 the program returns 1.

- Path 2: the program terminates at line 9. If the program goes into this block, $b$ divides $a$. Since $b$ is the greatest possible divisor of itself, this means that $\gcd(a,b) = b$, and $b$ is returned at line 9.

- Path 3: the program terminates at line 11. We need to check that the recursive call satisfies its preconditions and is called on a smaller instance. Note that $b$ and $(a \mod b)$ are both at least 1, and $(a \mod b) < b$, so the preconditions are satisfied. Since $a + b > (a \mod b) + b$, the sum of the inputs decreases, and so the recursive call is made on a smaller instance.

Therefore when the call completes, it returns gcd(b, a \mod b). Now we use the identity that  $ \gcd(a, b) = \gcd(b, a \mod b) $ to conclude that the original call returns the correct answer.

Example. We now look at a recursive example on lists. Here we consider a randomized binary search – this is worse than regular binary search in practice, but is useful for our purposes because it shows that the correctness of binary search doesn't depend on the size of the recursive calls.

def rand_bin_search(A, x):

    Pre: A is a sorted list of numbers, and x is a number
    Post: Returns true if and only if x is an element of A
    if len(A) == 0:
        return false
    else if len(A) == 1:
        return A[0] == x
    else:
        guess = a random number from 0 to len(A) - 1, inclusive
        if A[guess] == x:
            return true
        else if A[guess] > x:
            return rand_bin_search(A[0..guess-1], x)
    else:
        return rand_bin_search(A[guess+1..len(A)-1], x)

Proof of correctness. Here there are five different program paths. We'll check three of them, and leave the others as an exercise:

If you recall the example of using complete induction on ordered pairs, taking the sum of the two components was the size measure we used there, too.

How is it similar to quicksort?

- Path 1: the program terminates at line 7. This happens when A is empty; if this happens, x is certainly not in A, so the program returns the correct value (false).

- Path 2: the program terminates at line 9. We compare  $ A[0] $ to x, returning true if they are equal, and false otherwise. Note that if they aren't equal, then x cannot be in A, since A has only one element (its length is one).

- Path 4: the program terminates at line 15. This happens when  $ \text{len}(A) > 1 $, and  $ A[\text{guess}] > x $. Because A is sorted, and  $ A[\text{guess}] > x $, for every index  $ i \geq \text{guess} $,  $ A[i] > x $. Therefore the only way x could appear in A is if it appeared at an index smaller than guess.

Now, let us handle the recursive call. Since guess  $ \leq len(A) - 1 $, we have that guess -1  $ \leq len(A) - 2 $, and so the length of the list in the recursive call is at most  $ len(A) - 1 $; so the recursive call happens on a smaller instance. Therefore, when the recursive call returns, the postcondition is satisfied: it returns true if and only if x appears in  $ A[0..guess-1] $. The original function call then returns this value; by the discussion in the previous paragraph, this is the correct value to return, so the postcondition is satisfied.

#### Iterative Programs

In this section, we'll discuss how to handle loops in our code. So far, we have been able to determine the exact sequence of steps in each program path (e.g., "Lines 1, 2, 4, and 6 execute, and then the program returns"). However, this is not the case when we are presented with a loop, because the sequence of steps depends on the number of times the loop iterates, which in turn depends on the input (e.g., the length of an input list). Thus our argument for correctness cannot possibly go step by step!

Instead, we treat the entire loop as a single unit, and give a correctness argument specifically for it separately. But what do we mean for a loop to be "correct"? Consider the following function.

We've treated recursive calls as "black boxes" that behave nicely (i.e., can be treated as a single step) as long as their preconditions are satisfied and they are called on smaller inputs.

def avg(A):
    ...

    Pre: A is a non-empty list of numbers
    Post: Returns the average of the numbers in A

6 sum = 0
7 i = 0
8 while i < len(A):
9 sum += A[i]
10 i += 1
11 return sum / len(A)

This is the sort of program you wrote in CSC108. Intuitively, it is certainly correct — why? The “hard” work is done by the loop, which calculates the sum of the elements in A. The key is to prove that this is what the loop does. Coming out of first-year programming, most of you would be comfortable saying that the variable sum starts with value 0 before the loop, and after the loop ends it contains the value of the sum of all elements in A. But what can we say about the value of sum while the loop is running?

Clearly, the loop calculates the sum of the elements in A one element at a time. After some thought, we determine that the variable sum starts with value o and in the loop takes on the values A[0], then A[0] + A[1], then A[0] + A[1] + A[2], etc. We formalize this by defining a loop invariant for this loop. A loop invariant is a predicate that is true every time the loop-condition is checked (including the check that terminates the loop). Usually, the predicate will depend on which iteration the loop is on, or more generally, the value(s) of the program variable(s) associated with the loop. For example, in avg, the loop invariant corresponding to our previous intuition is

 $$ P(i,sum):sum=\sum_{k=0}^{i-1}A[k] $$

The i and sum in the predicate really correspond to the values of those variables in the code for avg. That is, this predicate is stating a property of these variables in the code.

Unfortunately, this loop invariant isn't quite right; what if  $ i > len(A) $? Then the sum is not well-defined, since, for example, A[len(A)] is undefined. This can be solved with a common technique for loop invariants: putting bounds on “loop counter” variables, as follows:

 $$ Inv(i,sum):0\leq i\leq len(A)\land sum=\sum_{k=0}^{i-1}A[k]. $$

This ensures that the sum is always well-defined, and has the added benefit of explicitly defining a possible range of values on i.

By convention, the empty sum  $ \sum_{k=0}^{-1} A[k] $ evaluates to 0.

In general, the fewer possible values a variable takes on, the fewer cases you have to worry about in your code.

A loop invariant is correct if it is always true at the beginning of every loop iteration, including the loop check that fails, causing the loop to terminate. This is why we allowed  $ i \leq len(A) $ rather than just  $ i < len(A) $ in the invariant.

How do we prove that loop invariants are correct? The argument is yet another application of induction:

- First, we argue that the loop invariant is satisfied when the loop is reached. (This is arrow (1) in the diagram)

- Then, we argue that if the loop invariant is satisfied at the beginning of an iteration, then after the loop body executes once (i.e., one loop iteration occurs), the loop invariant still holds. (Arrow (2))

- Finally, after proving that the loop invariant is correct, we show that if the invariant holds when the loop ends, then the postcondition will be satisfied when the program returns. (Arrow (3))

Though this is basically an inductive proof, as was the case for recursive programs, we won’t hold to the formal induction structure here.

Example. Let us formally prove that \textit{avg} is correct. The main portion of the proof will be the proof that our loop invariant \textit{Inv}(i,sum) is correct.

Proof. When the program first reaches the loop, i = 0 and sum = 0. Plugging this into the predicate yields

 $$ Inv(0,0):\quad0\leq0\leq len(A)\land0=\sum_{k=0}^{-1}A[k], $$

which is true (recall the note about the empty sum from earlier).

Now suppose the loop invariant holds when $i = i_{0}$, at the beginning of a loop iteration. Let $\text{sum}_{0}$ be the value of the variable $\text{sum}$ at this time. The loop invariant we are assuming is the following:

 $$ Inv(i_{0},sum_{0}):\quad0\leq i_{0}\leq len(A)\land sum_{0}=\sum_{k=0}^{i_{0}-1}A[k]. $$

What happens next? The obvious answer is “the loop body runs,” but this misses one subtle point: if  $ i_0 = len(A) $ (which is allowed by the loop invariant), the body of the loop doesn’t run, and we don’t need to worry about this case, since we only care about checking what happens to the invariant when the loop actually runs.

If we wanted to be precise, we would do induction on the number of loop iterations executed.

Assume that $i_0 < len(A)$, so that the loop body runs. What happens in one iteration? Two things: sum increases by $A[i_0]$, and i increases by 1. Let $sum_1$ and $i_1$ be the values of sum and i at the end of the loop iteration. We have $sum_1 = sum_0 + A[i_0]$ and $i_1 = i_0 + 1$. Our goal is to prove that the loop invariant holds for $i_1$ and $sum_1$, i.e.,

 $$ Inv(i_{1},sum_{1}):\quad0\leq i_{1}\leq len(A)\land sum_{1}=\sum_{k=0}^{i_{1}-1}A[k]. $$

Let us check that the loop invariant is still satisfied by  $ sum_1 $ and  $ i_1 $. First,  $ 0 \leq i_0 < i_0 + 1 = i_1 \leq len(A) $, where the first inequality came from the loop invariant holding at the beginning of the loop, and the last inequality came from the assumption that  $ i_0 < len(A) $. The second part of Inv can be checked by a simple calculation:

 $$ \begin{aligned}sum_{1}&=sum_{0}+A[i_{0}]\\&=\left(\sum_{k=0}^{i_{0}-1}A[k]\right)+A[i_{0}]&\text{(by}Inv(i_{0},sum_{0}))\\&=\sum_{k=0}^{i_{0}}A[k]\\&=\sum_{k=0}^{i_{1}-1}A[k]&\text{(Since}i_{1}=i_{0}+1)\\ \end{aligned} $$

Therefore the loop invariant always holds.

The next key idea is that when the loop ends, variable i has value  $ len(A) $, since by the loop invariant it always has value  $ \leq len(A) $, and if it were strictly less than  $ len(A) $, another iteration of the loop would run. Then by the loop invariant, the value of sum is  $ \sum_{k=0}^{len(A)-1} A[k] $, i.e., the sum of all the elements in A! The final step is to continue tracing until the program returns, which in this case takes just a single step: the program returns sum / len(A). But this is exactly the average of the numbers in A, because the variable sum is equal to their sum! Therefore the postcondition is satisfied.

Note the deep connection between the loop invariant and the post-condition. There are many other loop invariants we could have tried to prove: for example,  $ Inv(i,sum) : i + sum \geq 0 $. But this wouldn't have helped at all in proving the postcondition! When confronting more problems on your own, it will be up to you to determine the right loop invariants for the job. Keep in mind that choosing loop invariants can

That might seem like a lot of writing to get to what we said paragraphs ago, but this is a formal argument that confirms our intuition.

We also implicitly use here the mathematical definition of “average” as the sum of the numbers divided by how many there are.

usually be done by either taking a high-level approach and mimicking something in the postcondition or taking a low-level approach by carefully tracing through the code on test inputs to try to find patterns in the variable values.

One final warning before we move on: loop invariants describe relationships between variables at a specific moment in time. Students often try to use loop invariants to capture how variables change over time (e.g., "i will increase by 1 when the loop runs"), which creates massive headaches because determining how the code works is the meat of a proof, and shouldn't be shoehorned into a single predicate! When working with more complex code, we take the view that loop invariants are properties that are preserved, even if they don't describe exactly how the code works or exactly what happens! This flexibility is what makes correctness proofs manageable.

Example. Here we consider a numerical example: a low-level implementation of multiplication.

def mult(a,b):
    ...

    Pre: a and b are natural numbers

    Post: returns a * b

    ...

    m = 0

    count = 0

    while count < b:
        m += a

        count += 1

    return m

Proof of correctness. The key thing to figure out here is how the loop accomplishes the multiplication. It's clear what it's supposed to do: the variable m changes from o at the beginning of the loop to a*b at the end. How does this change happen? One simple thing we could do is make a table of values of the variables m and count as the loop progresses:

<table border=1 style='margin: auto; word-wrap: break-word;'><tr><td style='text-align: center; word-wrap: break-word;'>m</td><td style='text-align: center; word-wrap: break-word;'>count</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>0</td><td style='text-align: center; word-wrap: break-word;'>0</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>a</td><td style='text-align: center; word-wrap: break-word;'>1</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>2a</td><td style='text-align: center; word-wrap: break-word;'>2</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>3a</td><td style='text-align: center; word-wrap: break-word;'>3</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>$ \vdots $</td><td style='text-align: center; word-wrap: break-word;'>$ \vdots $</td></tr></table>

Aha: m seems to always contain the product of a and count; and, when the loop ends, count = b! This leads directly to the following loop invariant (including the bound on count):

 $$ Inv(m,count):m=a\times count\land count\leq b $$

Consider an execution of the code, with the preconditions satisfied by the inputs. Then when the loop is first encountered,  $ m = 0 $ and  $ count = 0 $, so  $ m = a \times count $, and  $ count \leq b $ (since  $ b \in \mathbb{N} $).

Now suppose the loop invariant holds at the beginning of some iteration, with $m = m_0$ and $count = count_0$. Furthermore, suppose $count_0 < b$, so the loop runs. When the loop runs, $m$ increases by a and count increases by 1. Let $m_1$ and $count_1$ denote the new values of $m$ and $count$; so $m_1 = m_0 + a$ and $count_1 = count_0 + 1$. Since $Inv(m_0, count_0)$ holds, we have

 $$ \begin{aligned}m_{1}&=m_{0}+a\\&=a\times count_{0}+a\\&=a(count_{0}+1)\\&=a\times count_{1}\end{aligned} $$

(by invariant)

Moreover, since we've assumed  $ count_0 < b $, we have that  $ count_1 = count_0 + 1 \leq b $. So  $ Inv(m_1, count_1) $ holds.

Finally, when the loop terminates, we must have count = b, since by the loop invariant count ≤ b, and if count < b another iteration would occur. Then by the loop invariant again, when the loop terminates, m = ab, and the function returns m, satisfying the postcondition.

#### Termination

Unfortunately, there is a slight problem with all the correctness proofs we have done so far. We’ve used phrases like “when the recursive call ends” and “when the loop terminates”. But how do we know that the recursive calls and loops end at all? That is, how do we know that a program does not contain an infinite loop or infinite recursion?

Explicitly, we assume that  $ Inv(m_{0}, count_{0}) $ holds.

This is a serious issue: what beginning programmer hasn't been foiled by either of these errors?

The case for recursion is actually already handled by our implicit induction proof structure. Recall that the predicate in our induction proofs is that f is correct on inputs of size $n$; part of the definition of correctness is that the program terminates. Therefore as long as the induction structure holds — i.e., that the recursive calls are getting smaller and smaller — termination comes for free.

The case is a little trickier for loops. As an example, consider the loop in avg. Because the loop invariant Inv(i,sum) doesn't say anything about how i changes, we can't use it to prove that the loop terminates. But for most loops, including this one, it is "obvious" why they terminate, because they typically have counter variables that iterate through a fixed range of values.

This argument would certainly convince us that the avg loop terminates, and in general all loops with this form of loop counter terminate. However, not all loops you will see or write will have such an obvious loop counter. Here’s an example:

def collatz(n):
    '' Pre: n is a natural number ""
    curr = n
    while curr > 1:
        if curr is even:
            curr = curr // 2
        else:
            curr = 3 * curr + 1

Therefore we’ll now introduce a formal way of proving loop termination. Recall that our correctness proofs of recursive functions hinged on the fact that the recursive calls were made on smaller and smaller inputs, until some base case was reached. Our strategy for loops will draw inspiration from this: we associate with the loop a loop variant v that has the following two properties:

(1) v decreases with each iteration of the loop

(2) v is always a natural number at the beginning of each loop iteration

If such a $v$ exists, then at some point $v$ won't be able to decrease any further (because $o$ is the smallest natural number), and therefore the loop cannot have any more iterations. This is analogous to inputs to recursive calls getting smaller and smaller until a base case is reached.

The counter role is played by the variable i, which goes through the range $\{0,1,\ldots,len(A)\}$.

In fact, it is an open question in mathematics whether this function halts on all inputs or not. If only we had a computer program that could tell us whether it does!

loop termination

loop variant

While this is not the only strategy for proving termination, it turns out to be suitable for most loops involving numbers and lists. When you study more advanced data structures and algorithms, you will discuss more complex arguments for both correctness and termination.

Let us illustrate this technique on our avg loop.

Example. Proof of termination of avg. Even though we've already observed that the loop has a natural loop counter variable i, this variable increases with each iteration. Instead, our loop variant will be $v = len(A) - i$. Let us check that $v$ satisfies the properties (1) and (2):

(1) Since at each iteration i increases by 1, and  $ len(A) $ stays the same,  $ v = len(A) - i $ decreases by 1 on each iteration.

(2) Note that $i$ and $len(A)$ are both always natural numbers. But this alone is not enough to conclude that $v \in \mathbb{N}$; for example, $3,5 \in \mathbb{N}$ but $(3-5) \notin \mathbb{N}$. But the loop invariant we proved included the predicate $0 \leq i \leq len(A)$, and because of this we can conclude that $len(A) - i \geq 0$, so $len(A) - i \in \mathbb{N}$.

Since we have established that v is a decreasing, bounded variant for the loop, this loop terminates, and therefore avg terminates (since every other line of code is a simple step that certainly terminates).

Notice that the above termination proof relied on i increasing by 1 on each iteration, and that i never exceeds len(A). That is, we basically just used the fact that i was a standard loop counter. Here is a more complex example where there is no obvious loop counter.

Example. Prove that the following function terminates:

def term_ex(x,y):
    *** Pre: x and y are natural numbers. ***
    a = x
    b = y
    while a > 0 or b > 0:
        if a > 0:
            a -= 1
        else:
            b -= 1
        return x * y

This is a major reason we include such loop counter bounds on the loop invariant.

Proof. Intuitively, the loop terminates because when the loop runs, either $a$ or $b$ decreases, and will stop when $a$ and $b$ reach 0. To make this argument formal, we need the following loop invariant: $a,b \geq 0$, whose proof we leave as an exercise.

The loop variant we define is  $ v = a + b $. Let us prove the necessary properties for v:

- In the loop, either $a$ decreases by 1, or $b$ decreases by 1. In either case, $v = a + b$ decreases by 1. Therefore $v$ is decreasing.

• Since our loop invariant says that  $ a, b \geq 0 $, we have that  $ v \geq 0 $ as well. Therefore  $ v \in \mathbb{N} $.

#### Exercises

1. Here is some code that recursively determines the smallest element of a list. Give pre- and postconditions for this function, then prove it is correct according to your specifications.

def recmin(A):
    if len(A) == 1:
        return A[0]
    else:
    m = len(A) // 2
    min1 = recmin(A[0..m-1])
    min2 = recmin(A[m..len(A)-1])
    return min(min1, min2)

2. Prove that the following code is correct, according to its specifications.

def sort_colours(A):
    ...

    Pre: A is a list whose elements are either 'red' or 'blue'
    Post: All red elements in A appear before all blue ones
    ...

    i = 0
    j = 0
    while i < len(A):
        if A[i] is red:
            swap A[i], A[j]
            j += 1
        i += 1

3. Prove the following loop invariant for the loop in term_ex:  $ Inv(a, b) $  $ a, b \geq 0 $.

4. Consider the following modification of the term_exexample.

def term_ex_2(x,y):
    '' Pre: x and y are natural numbers ""
    a = x
    b = y
    while a >= 0 or b >= 0:
        if a > 0:
            a -= 1
        else:
            b -= 1
        return x * y

(a) Demonstrate via example that this doesn't always terminate.

(b) Show why the proof of termination given for term_ex fails.

5. For each of the following, state pre- and postconditions that capture what the program is designed to do, then prove that it is correct according to your specifications.

Don't forget to prove termination (even though this is pretty simple). It's easy to forget about this if you aren't paying attention.

(a)

def mod(n, d):
    r = n
    while r >= d:
        r -= d
    return r

(b)

def div(n, d):
    r = n
    q = 0
    while r >= d:
        r -= d
    q += 1
    return q

(c)

def lcm(a,b):
    x = a
    y = b
    while x != y:
        if x < y:
            x += a
        else:
            y += b
    return x

(d)

def div3(s):
    r = 0
    t = 1
    i = 0
    while i < len(s):
        r += t * s[i]
        t += -1
        i += 1
    return r mod 3 == 0

(e)

def count_zeroes(L):
    z = 0
    i = 0
    while i < len(L):
        if L[i] == 0:
            z += 1
        i += 1
    return z

(f)

def f(n):
    r = 2
    i = n
    while i > 0:
        r = 3*r -2

6 i -= 1
7 return r

6. Consider the following code.

def f(x):
    '' Pre: x is a natural number ""
    a = x
    y = 10
    while a > 0:
        a -= y
        y -= 1
    return a * y

(a) Give a loop invariant that characterizes the values of a and y.

(b) Show that sometimes this code fails to terminate.

7. In this question, we study two different algorithms for exponentiation: a recursive and iterative algorithm. First, state pre- and postconditions that the algorithms must satisfy (they're the same for the two). Then, prove that each algorithm is correct according to the specifications.

(a)

def exp_rec(a, b):
    if b == 0:
        return 1
    else if b mod 2 == 0:
        x = exp_rec(a, b / 2)
        return x * x
    else:
    x = exp_rec(a, (b - 1)/2)
    return x * x * a

(b)

def exp_iter(a, b):
    ans = 1
    mult = a
    exp = b

while exp > 0:
    if exp mod 2 == 1:
        ans += mult
    mult = mult * mult
    exp = exp // 2
    return ans

8. Prove that the following function is correct. Warning: this one is probably the most difficult of these exercises. But, it runs in linear time – pretty amazing!

def majority(A):
    Pre: A is a list with more than half its entries equal to x
    Post: Returns the majority element x
    c = 1
    m = A[0]
    i = 1
    while i <= len(A) - 1:
        if c == 0:
            m = A[i]
            c == 1
        else if A[i] == m:
            c += 1
        else:
            c -= 1
        i += 1
    return m

9. Here we study yet another sorting algorithm, bubblesort.

def bubblesort(L):
    Pre: L is a list of numbers
    Post: L is sorted
    k = 0
    while k < len(L):
        i = 0
        while i < len(L) - k:
            if L[i] > L[i+1]:
                swap L[i] and L[i+1]
                i += 1
        k += 1

(a) State and prove an invariant for the inner loop.

(b) State and prove an invariant for the outer loop.

(c) Prove that bubblesort is correct, according to its specifications.

10. Consider the following generalization of the min function.

def extract(A, k):
    pivot = A[0]
    # Use partition from quicksort
    L, G = partition(A[1..len(A) - 1], pivot)
    if len(L) == k - 1:
        return pivot
    else if len(L) >= k:
        return extract(L, k)
    else:
        return extract(G, k - len(L) - 1)

(a) Prove that this algorithm is correct.

(b) Analyse the worst-case running time of this algorithm. Hint: this algorithm is known as quickselect, and is pretty obviously related to quicksort.
