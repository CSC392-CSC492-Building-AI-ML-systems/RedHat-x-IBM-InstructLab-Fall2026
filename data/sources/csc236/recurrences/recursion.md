# Recursion

Source: David Liu, *Introduction to the Theory of Computation: Lecture Notes and Exercises for CSC236*, with UTM edits by Daniel Zingaro.

Now, programming! In this chapter, we will apply what we’ve learned about induction to study recursive algorithms. In particular, we will learn how to analyse the time complexity of recursive programs, for which the runtime on an input of size  $ n $ depends on the runtime on smaller inputs. Unsurprisingly, this is tightly connected to the study of recursively defined (mathematical) functions; we will discuss how to go from a recurrence relation like  $ f(n+1) = f(n) + f(n-1) $ to a closed form expression like  $ f(n) = 2^n + n^2 $. For recurrences of a special form, we will see how the Master Theorem gives us immediate, tight asymptotic bounds. These recurrences will be used for divide-and-conquer algorithms; you will gain experience with this common algorithmic paradigm and even design algorithms of your own.

#### Measuring Runtime

Recall that one of the most important properties of an algorithm is how long it takes to run. We can use the number of steps as a measurement of running time; but reporting an absolute number like “10 steps” or “1 000 000 steps” an algorithm takes is pretty meaningless unless we know how “big” the input was, since of course we’d expect algorithms to take longer on larger inputs. So a more meaningful measure of runtime is “10 steps when the input has size 2” or “1 000 000 steps when the input has size 300” or even better, “n² + 2 steps when the input has size n.” But as you probably remember from CSC148, counting an exact number of steps is often tedious and arbitrary, so we care more about the Big-O (asymptotic) analysis of an algorithm.

In CSC148 and earlier in this course, you analysed the runtime of iterative algorithms. As we've mentioned several times by now, induction is very similar to recursion; since induction has been the key idea of the course so far, it should come as no surprise that we'll turn our attention to recursive algorithms now!

Recall that asymptotic bounds involve

Big-O, and are less precise than exact

expressions.

In this course, we will mainly care about the upper bound on the worst-case runtime of algorithms; that is, the absolute longest an algorithm could run on a given input size n.

## A Simple Recursive Function

Consider the following simple recursive function, which you probably saw in CSC148:

def fact(n):
    if n == 1:
        return 1
    else:
        return n * fact(n-1)

How would you informally analyse the runtime of this algorithm? One might say that the recursion depth is $n$, and at each call there is just one step other than the recursive call, so the runtime is $\mathcal{O}(n)$, i.e., linear time. But in performing a more thorough step-by-step analysis, we reach a stumbling block with the recursive call fact$(n-1)$: the runtime of fact on input $n$ depends on its runtime on input $n-1$. Let's see how to deal with this relationship, using mathematics and induction.

#### Recursively Defined Functions

You should all be familiar with standard function notation: $f(n) = n^{2}$, $f(n) = n \log n$, or the slightly more unusual (but no less meaningful) $f(n) = $ “the number of distinct prime factors of $n$.” There is a second way of defining functions using recursion, e.g.,

 $$ f(n)=\begin{cases}0,&if n=0\\f(n-1)+2n-1,&if n\geq1\end{cases} $$

Recursive definitions allow us to capture marginal or relative difference between function values, even when we don’t know their exact values. But recursive definitions have a significant downside: we can only calculate large values of $f$ by computing smaller values first. For calculating extremely large, or symbolic, values of $f$ (like $f(n^2 + 3n)$), a recursive definition is inadequate; what we would really like is a closed form expression for $f$, one that doesn’t depend on other values of $f$. In this case, the closed form expression for $f$ is $f(n) = n^2$.

All code in this course will be in Python-like pseudocode. The syntax and methods will be mostly Python, with some English making the code more readable and/or intuitive. We'll expect you to follow a similar style.

In CSC148, it was surely claimed that this function computes n! and we'll see later in this course how to formally prove that this is what the function does.

recursively defined function

You will prove this in the Exercises.

Before returning to our earlier factorial example, let us see how to apply this to a more concrete example.

Example. There are exactly two ways of tiling a 3-by-2 grid using tri-ominoes, shown to the right:

Develop a recursive definition for $f(n)$, the number of ways of tiling a 3-by-n grid using triominoes for $n \geq 1$. Then, find a closed form expression for $f$.

##### Solution:

Note that if $n = 1$, there are no possible tilings, since no triomino will fit in a 3-by-1 board. We have already observed that there are 2 tilings for $n = 2$. Suppose $n > 2$. The key idea to get a recurrence is that for a 3-by-$n$ block, first consider the upper-left square. In any tiling, there are only two possible triomino placements that can cover it (these orientations are shown in the diagram above). Once we have fixed one of these orientations, there is only one possible triomino orientation that can cover the bottom-left square (again, these are the two orientations shown in the figure).

So there are exactly two possibilities for covering both the bottom-left and top-left squares. But once we’ve put these two down, we’ve tiled the leftmost 3-by-2 part of the grid, and the remainder of the tiling really just tiles the remaining 3-by-(n-2) part of the grid; there are  $ f(n-2) $ such tilings. Since these two parts are independent of each other, we get the total number of tilings by multiplying the number of possibilities for each. Therefore the recurrence relation is:

 $$ f(n)=\begin{cases}0,&if n=1\\2,&if n=2\\2f(n-2),&if n>2\end{cases} $$

Now that we have the recursive definition of $f$, we would like to find its closed form expression. The first step is to guess the closed form expression, by a “brute force” approach known as repeated substitution. Intuitively, we’ll expand out the recursive definition until we find a pattern.

 $$ \begin{aligned}f(n)&=2f(n-2)\\&=4f(n-4)\\&=8f(n-6)\\&\vdots\\&=2^{k}f(n-2k)\end{aligned} $$

Because we've expressed $f(n)$ in terms of $f(n-2)$, we need two base cases – otherwise, at $n=2$ we would be stuck, as $f(0)$ is undefined.

So much of mathematics is finding patterns.

There are two possibilities. If $n$ is odd, say $n = 2m + 1$, then we have $f(n) = 2^m f(1) = 0$, since $f(1) = 0$. If $n$ is even, say $n = 2m$, then $f(n) = 2^{m-1} f(2) = 2^{m-1} \cdot 2 = 2^m$. Writing our final answer in terms of $n$ only:

 $$ f(n)=\begin{cases}0,&if n is odd\\2^{\frac{n}{2}},&if n is even\end{cases} $$

Thus we’ve obtained a closed form formula $f(n)$ – except the $\vdots$ in our repeated substitution does not constitute a formal proof! When you saw the $\vdots$, you probably interpreted it as “repeat over and over again until...” and we already know how to make this thinking formal: induction! That is, given the recursive definition of $f$, we can prove using complete induction that $f(n)$ has the closed form given above. This is a rather straightforward argument, and we leave it for the Exercises.

We will now apply this technique to our earlier example.

Example. Analyse the asymptotic worst-case running time of fact (n), in terms of n.

##### Solution:

Let $T(n)$ denote the worst-case running time of fact on input $n$. In this course, we will ignore exact step counts entirely, replacing these counts with constants.

The base case of this method is when $n=1$; in this case, the if block executes and the method returns 1. This is done in constant time, and so we can say that $T(1)=c$ for some constant $c$.

What if $n > 1$? Then fact makes a recursive call, and to analyse the runtime we consider the recursive and non-recursive parts separately. The non-recursive part is simple: only a constant number of steps occur (the if check, multiplication by $n$, and the return), so let's say the non-recursive part takes $d$ steps. What about the recursive part? The recursive call is fact$(n-1)$, which has worst-case runtime $T(n-1)$, by definition! Therefore when $n > 1$ we get the recurrence relation $T(n) = T(n-1) + d$. Putting this together with the base case, we get the full recursive definition of $T$:

 $$ T(n)=\begin{cases}c,&if n=1\\T(n-1)+d,&if n>1\end{cases} $$

Now, we would like to say that  $ T(n) = \mathcal{O}(??) $, but to do so, we really need a closed form definition of T. Once again, we use repeated

Why complete and not simple induction? We need the induction hypothesis to work for n-2, and not just n-1.

Constant always means “independent of input size.”

substitution.

 $$ \begin{aligned}T(n)&=T(n-1)+d\\&=\left(T(n-2)+d\right)+d=T(n-2)+2d\\&=T(n-3)+3d\\&\vdots\\&=T(1)+(n-1)d\\&=c+(n-1)d\quad&(Since~T(1)=c)\end{aligned} $$

Thus we've obtained the closed form formula $T(n) = c + (n-1)d$, modulo the $\therefore$ As in the previous example, we leave proving this closed form as an exercise.

After proving this closed form, the final step is simply to convert this closed form into an asymptotic bound on $T$. Since $c$ and $d$ are constants with respect to $n$, we have that $T(n) = \mathcal{O}(n)$.

Now let's see a more complicated recursive function.

Example. Consider the following code for binary search.

def bin_search(A, x):

    Pre: A is a sorted list (non-decreasing order).
    Post: Returns True if and only if x is in A.
    if len(A) == 0:
        return False
    else if len(A) == 1:
        return A[0] == x
    else:
    m = len(A) // 2  # Rounds down, like floor
    if x <= A[m-1]:
        return bin_search(A[0..m-1], x)
    else:
    return bin_search(A[m..len(A)-1], x)

We analyse the runtime of bin_search in terms of $n$, the length of the input list $A$. If $n = 0$ or $n = 1$, bin_search(A,x) takes constant time (note that it doesn't matter whether the constant is the same or different for 0 and 1).

What about when $n > 1$? Then some recursive calls are made, and we again look at the recursive and non-recursive steps separately. We

One notable difference from Python is

how we'll denote sublists. Here, we use

the notation A[i..j] to mean the slice

of the list A from index i to index j,

including A[i] and A[j].

include the computation of  $ A[\theta..m-1] $ and  $ A[m..len(A)-1] $ in the non-recursive part, since argument evaluation happens before the recursive call begins.

IMPORTANT ANNOUNCEMENT 1: We will interpret all list slicing operations  $ A[i..j] $ as constant time, even when i and j depend on the length of the list. See the discussion in the following section.

Interpreting list slicing as constant time, the non-recursive cost of bin_search is constant time. What about the recursive calls? In all possible cases, only one recursive call occurs. What is the size of the list of the recursive call? When either recursive call happens,  $ m = \left\lfloor \frac{n}{2} \right\rfloor $, meaning the recursive call either is on a list of size  $ \left\lfloor \frac{n}{2} \right\rfloor $ or  $ \left\lceil \frac{n}{2} \right\rceil $.

IMPORTANT ANNOUNCEMENT 2: In this course, we won't care about floors and ceilings. We'll always assume that the input sizes are "nice" so that the recursive calls always divide the list evenly. In the case of binary search, we'll assume that n is a power of 2.

With this in mind, we conclude that the recurrence relation for  $ T(n) $ is  $ T(n) = T\left(\frac{n}{2}\right) + d $. Therefore the full recursive definition of T is

 $$ T(n)=\left\{\begin{aligned}&c,&&if n\leq1\\ &T\left(\frac{n}{2}\right)+d,&&if n>1\end{aligned}\right. $$

Let us use repeated substitution to guess a closed form. Assume that  $ n = 2^k $ for some natural number k.

 $$ \begin{aligned}T(n)&=T\left(\frac{n}{2}\right)+d\\&=\left(T\left(\frac{n}{4}\right)+d\right)+d=T\left(\frac{n}{4}\right)+2d\\&=T\left(\frac{n}{8}\right)+3d\\&\vdots\\&=T\left(\frac{n}{2^{k}}\right)+kd\\&=T(1)+kd\quad(Since n=2^{k})\\&=c+kd\quad(Since T(1)=c)\\ \end{aligned} $$

Again, we omit floors and ceilings.

Interestingly, this is not the case in some programming languages – an alternative is “lazy evaluation.”

You may look in Vassos Hadzilacos' course notes for a complete handling of floors and ceilings. The algebra is a little more involved, but the bottom line is that the asymptotic analysis is unchanged.

Once again, we’ll leave proving this closed form to the Exercises. So  $ T(n) = c + kd $. This expression is quite misleading, because it seems to not involve an  $ n $, and hence be constant time - which we know is not the case for binary search! The key is to remember that  $ n = 2^k $, so  $ k = \log_2 n $. Therefore we have  $ T(n) = c + d \log_2 n $, and so  $ T(n) = \mathcal{O}(\log n) $.

### Aside: List Slicing vs. Indexing

In our analysis of binary search, we assumed that the list slicing operation  $ A[0..m-1] $ took constant time. However, this is not the case in Python and many other programming languages, which implement this operation by copying the sliced elements into a new list. Depending on the scale of your application, this can be undesirable for two reasons: this copying takes time linear in the size of the slice, and uses linear additional memory.

While we are not so concerned in this course about the second issue, the first can drastically change our runtime analysis (e.g., in our analysis of binary search). However, there is always another way to implement these algorithms without this sort of slicing that can be done in constant time, and without creating new lists. The key idea is to use variables to keep track of the start and end points of the section of the list we are interested in, but keep the whole list all the way through the computation. We illustrate this technique in our modified binary search:

def indexed_bin_search(A, x, first, last):
    if first > last:
        return False
    else if first == last:
        return A[first] == x
    else:
    m = (first + last + 1) // 2
    if x <= A[m-1]:
        return indexed_bin_search(A, x, first, m - 1)
    else:
        return indexed_bin_search(A, x, m, last)

In this code, the same list A is passed to each recursive call; the range of searched values, on the other hand, indeed gets smaller, as

the first and last parameters change. More technically, the size of the range, last - first + 1, decreases by a (multiplicative) factor of two at each recursive call.

Passing indices as arguments works well for recursive functions that work on smaller and smaller segments of a list. We’ve just introduced the most basic version of this technique. However, many other algorithms involve making new lists in more complex ways, and it is usually possible to make these algorithms in-place, i.e., to use a constant amount of extra memory, and do operations by changing the elements of the original list.

Because we aren't very concerned with this level of implementation detail in this course, we'll use the shortcut of interpreting list slicing as taking constant time, keeping in mind actual naive implementations take linear time. This will allow us to perform our runtime analyses without getting bogged down in clever implementation tricks.

## A Special Recurrence Form

In general, finding exact closed forms for recurrences can be tedious or even impossible. Luckily, we are often not really looking for a closed form solution to a recurrence, but an asymptotic bound. But even for this relaxed goal, the only method we have so far is to find a closed form and turn it into an asymptotic bound. In this section, we'll look at a powerful technique with the caveat that it works only for a special recurrence form.

We can motivate this recurrence form by considering a style of recursive algorithm called divide-and-conquer. We'll discuss this in detail in the next section, but for now consider the mergesort algorithm, which can roughly be outlined in three steps:

1. Divide the list into two equal halves.

2. Sort each half separately, using recursive calls to mergesort.

3. Merge each of the sorted halves.

def mergesort(A):
    if len(A) == 1:
        return A

else:
    m = len(A) // 2
    L1 = mergesort(A[0..m-1])

L2 = mergesort(A[m..len(A)-1]))
return merge(L1, L2)

def merge(A, B):
    i = 0
    j = 0
    C = []
    while i < len(A) and j < len(B):
        if A[i] <= B[j]:
            C.append(A[i])
            i += 1
        else:
            C.append(B[j])
        j += 1
    return C + A[i..len(A)-1] + B[j..len(B)-1] # List concatenation

Consider the analysis of $T(n)$, the runtime of mergesort(A) where $\text{len}(A) = n$. Steps 1 and 3 together take linear time. What about Step 2? Since this is the recursive step, we'd expect $T$ to appear here. There are two fundamental questions:

• What is the number of recursive calls?

- What is the size of the lists passed to the recursive calls?

From the written description, you should be able to intuit that there are two recursive calls, each on a list of size $\frac{n}{2}$. So the cost of Step 2 is $2T\left(\frac{n}{2}\right)$. Putting all three steps together, we get a recurrence relation

 $$ T(n)=2T\left(\frac{n}{2}\right)+c n. $$

This is an example of our special recurrence form:

 $$ T(n)=aT\left(\frac{n}{b}\right)+f(n), $$

where  $ a \in \mathbb{Z}^+ $,  $ b > 1 $ are constants and  $ f : \mathbb{N} \to \mathbb{R}^+ $ is some arbitrary function.

Careful implementations of mergesort can do step 1 in constant time, but merging always takes linear time.

Before we get to the Master Theorem, which gives us an immediate asymptotic bound for recurrences of this form, let's discuss some intuition. The special recurrence form has three parameters: a, b, and f. Changing how big they are affects the overall runtime:

- a is the “number of recursive calls”; the bigger a is, the more recursive calls, and the bigger we expect  $ T(n) $ to be.

For the last time, we'll point out that we ignore floors and ceilings.

Though we'll soon restrict f to ease the analysis of this recursive form.

- b determines the rate of decrease of the problem size; the larger b is, the faster the problem size goes down to 1, and the smaller  $ T(n) $ is.

-  $ f(n) $ is the cost of the non-recursive part; the bigger  $ f(n) $ is, the bigger  $ T(n) $ is.

We can further quantify this relationship by considering the following even more specific form:

 $$ f(n)=\left\{\begin{aligned}&c,&&if n=1\\ &af\left(\frac{n}{b}\right)+n^{k},&&if n>1\end{aligned}\right. $$

Suppose $n$ is a power of $b$, say $n = b^{r}$. Using repeated substitution,

 $$ \begin{aligned}f(n)&=a f\left(\frac{n}{b}\right)+n^{k}\\&=a\left(a f\left(\frac{n}{b^{2}}\right)+\frac{n^{k}}{b^{k}}\right)+n^{k}=a^{2}f\left(\frac{n}{b^{2}}\right)+n^{k}\left(1+\frac{a}{b^{k}}\right)\\&=a^{3}f\left(\frac{n}{b^{3}}\right)+n^{k}\left(1+\frac{a}{b^{k}}+\left(\frac{a}{b^{k}}\right)^{2}\right)\\&\vdots\\&=a^{r}f\left(\frac{n}{b^{r}}\right)+n^{k}\sum_{i=0}^{r-1}\left(\frac{a}{b^{k}}\right)^{i}\\&=a^{r}f(1)+n^{k}\sum_{i=0}^{r-1}\left(\frac{a}{b^{k}}\right)^{i}\quad(Since n=b^{r})\\&=c a^{r}+n^{k}\sum_{i=0}^{r-1}\left(\frac{a}{b^{k}}\right)^{i}\\&=c n^{\log_{b}a}+n^{k}\sum_{i=0}^{r-1}\left(\frac{a}{b^{k}}\right)^{i}\\ \end{aligned} $$

The latter term looks like a geometric series, for which we may use our geometric series formula. However, this only applies when the common ratio  $ \frac{a}{b^k} $ is not equal to 1. Therefore, there are two cases.

Case 1:  $ \frac{a}{b^k} = 1 $, so  $ a = b^k $. Taking logs, we have  $ \log_b a = k $. In this case, the expression becomes

 $$ \begin{aligned}f(n)&=c n^{k}+n^{k}\sum_{i=0}^{r-1}1^{i}\\&=c n^{k}+n^{k}r\\&=c n^{k}+n^{k}\log_{b}n\\&=\mathcal{O}(n^{k}\log n)\end{aligned} $$

Note that  $ r = \log_b n $, and so  $ a^r = a^{\log_b n} = b^{\log_b a \cdot \log_b n} = n^{\log_b a} $.

• Case 2:  $ a \neq b^{k} $. Then by the geometric series formula,

 $$ \begin{aligned}f(n)&=c n^{\log_{b}a}+n^{k}\left(\frac{1-\frac{a^{\prime}}{b^{k r}}}{1-\frac{a}{b^{k}}}\right)\\&=c n^{\log_{b}a}+n^{k}\left(\frac{1-\frac{n^{\log_{b}a}}{n^{k}}}{1-\frac{a}{b^{k}}}\right)\\&=\left(c-\frac{1}{1-\frac{a}{b^{k}}}\right)n^{\log_{b}a}+\left(\frac{1}{1-\frac{a}{b^{k}}}\right)n^{k}\\ \end{aligned} $$

There are two occurrences of $n$ in this expression: $n^{\log_b a}$ and $n^k$. Asymptotically, the higher exponent dominates; so if $\log_b a > k$, then $f(n) = \mathcal{O}(n^{\log_b a})$, and if $\log_b a < k$, then $f(n) = \mathcal{O}(n^k)$.

With this intuition in mind, let us now state the Master Theorem.

Theorem (Master Theorem). Let $T : \mathbb{N} \to \mathbb{R}^+$ be a recursively defined function with recurrence relation $T(n) = aT(n/b) + f(n)$, for some constants $a \in \mathbb{Z}^+$, $b > 1$, and $f : \mathbb{N} \to \mathbb{R}^+$. Furthermore, suppose $f(n) = \Theta(n^k)$ for some $k \geq 0$. Then we can conclude the following about the asymptotic complexity of $T$:

(1) If  $ k = \log_b a $, then  $ T(n) = \mathcal{O}(n^k \log n) $.

(2) If  $ k < \log_b a $, then  $ T(n) = \mathcal{O}(n^{\log_b a}) $.

(3) If  $ k > \log_b a $, then  $ T(n) = \mathcal{O}(n^k) $.

Let's see some examples of the Master Theorem in action.

Example. Consider the recurrence for mergesort:  $ T(n) = 2T(n/2) + dn $. Here a = b = 2, so  $ \log_2 2 = 1 $, while  $ dn = \Theta(n^1) $. Therefore Case 1 of the Master Theorem applies, and  $ T(n) = \mathcal{O}(n \log n) $, as we expected.

Example. Consider the recurrence  $ T(n) = 49T(n/7) + 50n^{\pi} $. Here,  $ \log_7 49 = 2 $ and  $ 2 < \pi $, so by Case 3 of the Master Theorem,  $ T(n) = \mathcal{O}(n^{\pi}) $.

Even though the Master Theorem is useful in a lot of situations, be sure you understand the statement of the theorem to see exactly when it applies (see Exercises for some questions investigating this).

#### Divide-and-Conquer Algorithms

Now that we have seen the Master Theorem, let's discuss some algorithms for which it can help us analyse the runtime! A key fea-

Master Theorem

ture of the recurrence form  $ aT(n/b) + f(n) $ is that each of the recursive calls has the same size. This naturally leads to the divide-and-conquer paradigm, which can be summarized as follows:

def divide-and-conquer(P):
    if P has "small enough" size:
        return solve_directly(P)
    else:
        divide P into smaller problems P_1, ..., P_k (same size)
        for i from l to k:
            # Solve each subproblem recursively
            s_i = divide_and_conquer(P_i)
        # combine the s_1 ... s_k to solve P
        return combine(s_1 ... s_k)

This is a very general template — in fact, it may seem exactly like your mental model of recursion so far, and certainly it is a recursive strategy. What distinguishes divide-and-conquer algorithms from a lot of other recursive procedures is that we divide the problem into two or more parts and solve the subproblems for each part, whereas recursive functions in general may make only a single recursive call, like in fact or bin\_search.

This introduction to the divide-and-conquer paradigm was deliberately abstract. However, we have already discussed one divide-and-conquer algorithm: mergesort! Let us now see two more examples of divide-and-conquer algorithms: fast multiplication and quicksort.

#### Fast Multiplication

Consider an algorithm for multiplying two numbers:  $ 1234 \times 5678 $. We might start by writing this as

 $$ (1*1000+2*100+3*10+4)*(5*1000+6*100+7*10+8) $$

Expanding this product requires 16 one-digit multiplications  $ (1 * 5,2 * 5,3 * 5,4 * 5,1 * 6, \ldots,4 * 8) $, and then some one-digit additions to add everything up. In general, multiplying two  $ n $-digit numbers this way requires  $ \mathcal{O}(n^2) $ one-digit operations.

Now, let's see a different way of making this faster. Using a divide-and-conquer approach, we want to split 1234 and 5678 into smaller

##### divide-and-conquer

An algorithmic paradigm is a general strategy for designing algorithms to solve problems. You will see many more such strategies in CSC373.

Another common non-divide-and-conquer recursive design pattern is taking a list, processing the first element, then recursively processing the rest of the list (and combining the results).

numbers:

 $$ 1234=12\cdot100+34,\quad5678=56\cdot100+78. $$

Now we use some algebra to write the product  $ 1234 \cdot 5678 $ as the combination of some smaller products:

 $$ \begin{aligned}1234\cdot5678&=(12\cdot100+34)(56\cdot100+78)\\&=(12\cdot56)\cdot10000+(12\cdot78+34\cdot56)\cdot100+34\cdot78\end{aligned} $$

So now instead of multiplying 4-digit numbers, we have shown how to find the solution by multiplying some 2-digit numbers, a much easier problem! Note that we aren't counting multiplication by powers of 10, since that amounts to just adding some zeroes to the end of the numbers.

Reducing 4-digit multiplication to 2-digit multiplication may not seem that impressive; but now, we'll generalize this to arbitrary n-digit numbers (the difference in multiplying 100-digit vs. 50-digit numbers may be more impressive).

Let x and y be n-digit numbers. For simplicity, assume n is a power of 2. Then we can divide x and y each into two halves:

 $$ x=10^{\frac{n}{2}}a+b $$

 $$ y=10^{\frac{n}{2}}c+d $$

Where $a,b,c,d$ are $\frac{n}{2}$-digit numbers. Then

 $$ x\cdot y=(a c)10^{n}+(a d+b c)10^{\frac{n}{2}}+b d. $$

We have found a mathematical identity that seems useful, and we can use this to develop a multiplication algorithm. Let's see some pseudocode:

def rec_mult(x,y):
    n = length of x # Assume x and y have the same length
    if n == 1:
        return x * y
    else:
        a = x // 10^(n//2)
        b = x % 10^(n//2)
        c = y // 10^(n//2)
        d = y % 10^(n//2)

        r = rec_mult(a, c)
        s = rec_mult(a, d)

On a computer, we would use base-2 instead of base-10 to take advantage of the “adding zeros,” which corresponds to (very fast) bit-shift machine operations.

The length of a number here refers to the number of digits in its decimal representation.

t = rec_mult(b, c)
u = rec_mult(b, d)

return r * 10^n + (s + t) * 10^(n/2) + u

Now, let's talk about the running time of this algorithm, in terms of the size $n$ of the two numbers. Note that there are four recursive calls; each call multiplies two numbers of size $\frac{n}{2}$, so the cost of the recursive calls is $4T\left(\frac{n}{2}\right)$. What about the non-recursive parts? Note that the final return step involves addition of $2n$-digit numbers, which takes $\Theta(n)$ time. Therefore we have the recurrence

 $$ T(n)=4T\left(\frac{n}{2}\right)+c n. $$

By the Master Theorem, we have  $ T(n) = \mathcal{O}(n^2) $.

So, this approach didn't help! We had an arguably more complicated algorithm that achieved the same asymptotic runtime as what we learned in elementary school! Moral of the story: Divide-and-conquer, like all algorithmic paradigms, doesn't always lead to "better" solutions!

In the case of fast multiplication, though, we can use more math to improve the running time. Note that the “cross term”  $ ad + bc $ in the algorithm required two multiplications to compute naïvely; however, it is correlated with the values of ac and bd with the following straightforward identity:

 $$ \begin{aligned}(a+b)(c+d)&=ac+(ad+bc)+bd\ $ a+b)(c+d)-ac-bd&=ad+bc\end{aligned} $$

So we can compute $ad + bc$ by calculating just one additional product $(a + b)(c + d)$ (together with $ac$ and $bd$ that we are calculating anyway). This trick underlies the multiplication algorithm of Karatsuba (1960).

def fast_rec_mult(x,y):
    n = length of x # Assume x and y have the same length
    if n == 1:
        return x * y
    else:
        a = x // 10^(n//2)
        b = x % 10^(n//2)
        c = y // 10^(n//2)
        d = y % 10^(n//2)

This is a serious lesson. It is not the case that everything we teach you works for every situation. It is up to you to carefully put together your knowledge to figure out how to approach problems!

10 p = fast_rec_mult(a + b, c + d)
11 r = fast_rec_mult(a, c)
12 u = fast_rec_mult(b, d)

13 return r * 10^n + (p - r - u) * 10^(n/2) + u

You can study the (improved!) runtime of this algorithm in the exercises.

#### Quicksort

In this section, we explore the divide-and-conquer sorting algorithm known as quicksort, which in practice is one of the most commonly used sorting algorithms. First, we give the pseudocode for this algorithm; note that this follows a very clear divide-and-conquer pattern. Unlike fast_rec_mult and mergesort, the hard work is done in the divide (partition) step, not the combine step. The combine step for quicksort can be made to take a constant amount of work.

def quicksort(A):
    if len(A) <= 1:
        # do nothing (A is already sorted)
    else:
        choose some element x of A (the "pivot")
    partition (divide) the rest of the elements of A into two lists:
    - L, the elements of A <= x
    - G, the elements of A > x
    sort L and G recursively
    combine the sorted lists in the order L + [x] + G
    set A equal to the new list

Before moving on, an excellent exercise is to take the above pseudocode and implement quicksort yourself. As we will discuss again and again, implementing algorithms yourself is the best way to understand them. Remember that the only way to improve your coding abilities is to code lots — even something as simple and common as sorting algorithms offers great practice. See the Exercises for more examples.

quicksort

Our naïve implementation below does list concatenation in linear time because of list slicing, but in fact a more clever implementation using indexing accomplishes this in constant time.

def quicksort(A):
    if len(A) <= 1:
        pass
    else:
        # Choose the final element as the pivot
        pivot = A[-1]

    # Partition the rest of A with respect to the pivot
    L, G = partition(A[0:-1], pivot)
    # Sort each list recursively
    quicksort(L)
    quicksort(G)

    # Combine
    sorted = L + [pivot] + G
    # Set A equal to the sorted list
    for i in range(len(A)):
        A[i] = sorted[i]

def partition(A, pivot):
    L = []
    G = []
    for x in A:
        if x <= pivot:
            L.append(x)
            else:
            G.append(x)
    return L, G

Let us try to analyse the running time  $ T(n) $ of this algorithm, where n is the length of the input list A. First, the base case n = 1 takes constant time. The partition method takes linear time, since it is called on a list of length n - 1 and contains a for loop that loops through all n - 1 elements. The Python list methods in the rest of the code also take linear time, though a more careful implementation could reduce this. But because partitioning the list always takes linear time, the non-recursive cost of quicksort is linear.

What about the costs of the recursive steps? There are two of them: quicksort(L) and quicksort(G), so the recursive cost in terms of L and G is  $ T(|L|) $ and  $ T(|G|) $. Therefore a potential recurrence is:

 $$ T(n)=\begin{cases}c,&if n\leq1\\T(|L|)+T(|G|)+dn,&if n>1\end{cases} $$

What's the problem with this recurrence? It depends on what L and G Here |A| denotes the length of the list A.

are, which in turn depends on the input array and the chosen pivot! In particular, we can't use either repeated substitution or the Master Theorem to analyse this function. In fact, the asymptotic running time of this algorithm can range from $\Theta(n \log n)$ to $\Theta(n^2)$, the latter of which is just as bad as bubbles sort!

This begs the question: why is quicksort so used in practice? Two reasons: quicksort takes  $ \Theta(n \log n) $ time “on average”, and careful implementations of quicksort yield better constants than other  $ \Theta(n \log n) $ algorithms like mergesort. These two facts together imply that quick-sort often outperforms other sorting algorithms in practice!

See the Exercises for details.

Average-case analysis is slightly more sophisticated than what we do in this course, but you can take this to mean that most of the time, on randomly selected inputs, quicksort takes  $ \Theta(n \log n) $ time.

#### Exercises

1. Let  $ f: \mathbb{N} \to \mathbb{N} $ be defined as

 $$ f(n)=\begin{cases}0,&if n=0\\f(n-1)+2n-1,&if n\geq1\end{cases} $$

Prove using induction that the closed form for $f$ is $f(n) = n^{2}$.

2. Recall the recursively defined function

 $$ f(n)=\begin{cases}0,&if n=1\\2,&if n=2\\2f(n-2),&if n>2\end{cases} $$

 $$ f(n)=\begin{cases}0,&if n is odd\\2^{\frac{n}{2}},&if n is even\end{cases} $$

3. Prove that the closed form expression for the runtime of fact is  $ T(n) = c + (n - 1)d $.

4. Prove that the closed form expression for the runtime of bin_search is  $ T(n) = c + d \log_2 n $.

5. Let  $ T(n) $ be the number of binary strings of length n in which there are no consecutive 1's. So  $ T(0) = 1 $,  $ T(1) = 2 $,  $ T(2) = 3 $, etc.

(a) Develop a recurrence for $T(n)$. Hint: think about the two possible cases for the last character.

(b) Find a closed form expression for  $ T(n) $.

(c) Prove that your closed form expression is correct using induction.

6. Repeat the steps of the previous question, except with binary strings where every 1 is immediately preceded by a o.

7. It is known that every full binary tree has an odd number of nodes. Let  $ T(n) $ denote the number of distinct full binary trees with n nodes. For example,  $ T(1) = 1 $,  $ T(3) = 1 $, and  $ T(7) = 5 $. Give a recurrence for  $ T(n) $, justifying why it is correct. Then, use induction to prove that  $ T(n) \geq \frac{1}{n}2^{(n-1)/2} $.

8. Consider the following recursively defined function

 $$ f(n)=\begin{cases}3,&if n=0\\7,&if n=1\\3f(n-1)-2f(n-2),&if n\geq2\end{cases} $$

Find a closed form expression for $f$, and prove that it is correct using induction.

9. Consider the following recursively defined function:

 $$ f(n)=\left\{\begin{aligned}&\frac{1}{5},&&if n=0\\ &\frac{1+f(n-1)}{2},&&if n\geq1\end{aligned}\right. $$

(a) Prove that for all  $ n \geq 1 $,  $ f(n+1) - f(n) < f(n) - f(n-1) $.

(b) Prove that for all  $ n \in \mathbb{N} $,  $ f(n) = 1 - \frac{4}{5 \cdot 2^n} $.

10. A block in a binary string is a maximal substring consisting of the same symbol. For example, the string 0100011 has four blocks: 0, 1, 000, and 11. Let  $ H(n) $ denote the number of binary strings of length n that have no odd length blocks of 1's. For example,  $ H(4) = 5 $:

 $$ \begin{array}{l} 0000 \quad 1100 \quad 0110 \quad 0011 \quad 1111 \end{array} $$

Develop a recursive definition for $H(n)$, and justify why it is correct. Then find a closed form for $H$ using repeated substitution.

11. Consider the following recursively defined function.

 $$ T(n)=\left\{\begin{aligned}&1,&&if~n=1\\ &4T\left(\frac{n}{2}\right)+\log_{2}n,&&otherwise\end{aligned}\right. $$

Use repeated substitution to come up with a closed form expression for $T(n)$, when $n = 2^k$; i.e., $n$ is a power of 2. You will need to use the following identity:

 $$ \sum_{i=0}^{n}i\cdot a^{i}=\frac{n\cdot a^{n+2}-(n+1)\cdot a^{n+1}+a}{(a-1)^{2}}. $$

A full binary tree is a binary tree where every node has either 0 or 2 children.

12. Analyse the worst-case runtime of fast_rec_mult.

13. Analyse the runtime of each of the following recursive algorithms. It's up to you to decide whether you should use repeated substitution or the Master Theorem to find the asymptotic bound.

(a)

def sum(A):
    if len(A) == 0:
        return 1
    else:
    return A[0] + sum(A[1..len(A)-1])

(b)

def fun(A):
    if len(A) < 2:
        return len(A) == 0
    else:
        return fun(A[2..len(A)-1])

(c)

def double_fun(A):
    n = len(A)
    if n < 2:
        return n
    else:
        return double_fun(A[0..n-2]) + double_fun(A[1..n-1])

(d)

def mystery(A):
    if len(A) <= 1:
        return 1
    else:
    d = len(A) // 4
    s = mystery(A[0..d-1])
    i = d
    while i < 3 * d:
        s += A[i]
    i += 1

s += mystery(A[3*d..len(A)-1])
return s

14. Recall the recurrence for the worst-case runtime of quicksort:

 $$ T(n)=\begin{cases}c,&if n\leq1\\T(|L|)+T(|G|)+dn,&if n>1\end{cases} $$

where L and G are the partitions of the list. Clearly, how the list is partitioned matters a great deal for the runtime of quicksort.

(a) Suppose the lists are always evenly split; that is,  $ |L| = |G| = \frac{n}{2} $ at each recursive call. Find a tight asymptotic bound on the runtime of quicksort using this assumption.

(b) Now suppose that the lists are always very unevenly split:  $ |L| = n - 2 $ and  $ |G| = 1 $ at each recursive call. Find a tight asymptotic bound on the runtime of quicksort using this assumption.

For simplicity, we'll ignore the fact that each list really would have size  $ \frac{n-1}{2} $.
