from ict_scanner.scanner import scan


if __name__ == "__main__":
    rows = scan()
    print("\nTop setups")
    for x in rows[:15]:
        if "error" in x:
            print(f"{x['symbol']:<14} ERROR {x['error']}")
            continue
        print(
            f"{x['symbol']:<14} {x['direction']:<5} "
            f"score={x['score']:>3} bias={x['htf_bias']:<7} mmxm={x['mmxm']}"
        )
