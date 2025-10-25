// web_platform/frontend/__tests__/RaceFilters.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { RaceFilters } from '@/components/RaceFilters';

describe('RaceFilters', () => {
  it('should render filter controls', () => {
    const handleChange = jest.fn();
    render(<RaceFilters onParamsChange={handleChange} isLoading={false} />);

    expect(screen.getByText('Race Filters')).toBeInTheDocument();
    expect(screen.getByText('Max Field Size')).toBeInTheDocument();
  });

  it('should persist parameters to localStorage', () => {
    const handleChange = jest.fn();
    const { rerender } = render(
      <RaceFilters onParamsChange={handleChange} isLoading={false} />
    );

    const slider = screen.getByDisplayValue('10');
    fireEvent.change(slider, { target: { value: '12' } });

    const stored = JSON.parse(localStorage.getItem('fortuna:filter-params') || '{}');
    expect(stored.maxFieldSize).toBe(12);
  });

  it('should reset to defaults', () => {
    const handleChange = jest.fn();
    render(<RaceFilters onParamsChange={handleChange} isLoading={false} />);

    const resetButton = screen.getByText('Reset to Defaults');
    fireEvent.click(resetButton);

    expect(handleChange).toHaveBeenCalledWith({
      maxFieldSize: 10,
      minFavoriteOdds: 2.5,
      minSecondFavoriteOdds: 4.0,
    });
  });
});
