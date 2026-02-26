from datetime import datetime, timedelta

SMALL = 115
LARGE = 150
STOP = 115


class Plan:
    """A single day in the original tapering plan."""

    __slots__ = ("date", "large", "small", "total")

    def __init__(
        self,
        day: datetime,
        smalls: int,
        larges: int,
        total: int,
    ) -> None:
        self.date = datetime.strftime(day, "%Y-%m-%d")
        self.small = str(smalls)
        self.large = str(larges)
        self.total = total

    def to_dict(self) -> dict[str, object]:
        """Convert Plan to a dictionary."""
        return {k: getattr(self, k) for k in self.__slots__}


def main(small_count: int, large_count: int, start_date: str) -> None:
    """Generate and print a caffeine tapering schedule as TSV."""
    day = datetime.strptime(start_date, "%Y-%m-%d")
    caffeine = (SMALL * small_count) + (LARGE * large_count)

    plan = []
    i = 1
    day = day - timedelta(days=2)
    plan.append(
        Plan(
            day=day,
            smalls=small_count,
            larges=large_count,
            total=caffeine,
        )
    )
    day = day + timedelta(days=1)
    plan.append(
        Plan(
            day=day,
            smalls=small_count,
            larges=large_count,
            total=caffeine,
        )
    )
    day = day + timedelta(days=1)
    while caffeine > STOP:
        if small_count == 2 and not large_count:
            large_count = 1
            small_count = 0
        elif large_count > 0:
            small_count += 1
            large_count -= 1
        else:
            large_count = small_count - 1
            small_count = 0

        new_caffeine = (SMALL * small_count) + (LARGE * large_count)
        last_caffeine = plan[i].total
        if 0 < last_caffeine - new_caffeine < 35:
            # If the step is too small, replace the prev step
            # with a bigger one.
            day = day - timedelta(days=2)
            plan[i - 1] = Plan(
                day=day,
                smalls=small_count,
                larges=large_count,
                total=new_caffeine,
            )
            day = day + timedelta(days=1)
            plan[i] = Plan(
                day=day,
                smalls=small_count,
                larges=large_count,
                total=new_caffeine,
            )
        else:
            plan.append(
                Plan(
                    day=day,
                    smalls=small_count,
                    larges=large_count,
                    total=new_caffeine,
                )
            )
            day = day + timedelta(days=1)
            plan.append(
                Plan(
                    day=day,
                    smalls=small_count,
                    larges=large_count,
                    total=new_caffeine,
                )
            )
            i += 2
        caffeine = new_caffeine
        day = day + timedelta(days=1)
    for i, p in enumerate(plan):
        fields = ("date", "small", "large", "total")
        row = "\t".join(str(getattr(p, f)) for f in fields)
        if i:
            row += "\t" + str(plan[i - 1].total - p.total)
        else:
            row += "\t0"
        print(row)


if __name__ == "__main__":
    main(small_count=0, large_count=3, start_date="2025-11-11")
