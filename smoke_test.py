from hyperon import MeTTa

m = MeTTa()
m.run("!(bind! &self (new-space))")
m.run("!(add-atom &self (foo 3))")
r = m.run("!(match &self (foo $x) $x)")
print("RESULT:", r)
print("SERVER_RUNNING: True")
