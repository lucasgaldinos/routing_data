class A:
  def m(self):
    return "A.m"


class B(A):
  def m(self):
    s = super()
    print("super()     ->", s, "| type:", type(s).__name__)
    print("super().m   ->", s.m)
    return "B.m + " + s.m()


print("B().m()     ->", B().m())
